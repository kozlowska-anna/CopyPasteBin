using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace CopyPasteBin.Stage0
{
    /// <summary>
    /// Stage 0 synthetic clipboard owner. It only ever WRITES fixed synthetic
    /// test data and never reads what was on the clipboard before.
    /// Running it replaces the current clipboard content.
    /// </summary>
    internal sealed class OwnerWindow : Form
    {
        // The base token of the test value. The probe must never print it; the
        // manual protocol searches the probe logs for it.
        public const string CanaryBase = "CPB-STAGE0-CANARY";
        private const string CanaryText = CanaryBase + " synthetic test value";

        private const int OpenAttempts = 400;
        private const int OpenDelayMs = 5;

        private readonly MetadataLog log;
        private readonly OwnerPlan plan;
        private IntPtr windowHandle = IntPtr.Zero;
        private uint formatExclude;
        private uint formatHistory;
        private uint formatCloud;
        private uint formatSynthetic;
        private bool stopped;

        public OwnerWindow(MetadataLog log, OwnerPlan plan)
        {
            this.log = log;
            this.plan = plan;
        }

        public void Start()
        {
            IntPtr created = Handle;
            if (created == IntPtr.Zero)
                log.Write("owner_error", "kind=no_window");
        }

        public void Stop()
        {
            if (stopped)
                return;
            stopped = true;
            Application.ExitThread();
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            windowHandle = Handle;
            formatExclude = Native.RegisterClipboardFormat(Native.FormatExcludeFromMonitors);
            formatHistory = Native.RegisterClipboardFormat(Native.FormatHistory);
            formatCloud = Native.RegisterClipboardFormat(Native.FormatCloud);
            formatSynthetic = Native.RegisterClipboardFormat(Native.FormatSynthetic);
        }

        protected override void OnHandleDestroyed(EventArgs e)
        {
            // Promised delayed data must not outlive this process.
            if (plan.Delayed && Native.GetClipboardOwner() == windowHandle)
            {
                bool emptied = false;
                if (Open())
                {
                    emptied = Native.EmptyClipboard();
                    Native.CloseClipboard();
                }
                log.Write("cleanup", "emptied_own_data=" + Fmt.Flag(emptied));
            }
            base.OnHandleDestroyed(e);
        }

        protected override void WndProc(ref Message m)
        {
            try
            {
                switch (m.Msg)
                {
                    case Native.WM_RENDERFORMAT:
                        OnRenderFormat(unchecked((uint)m.WParam.ToInt64()));
                        break;
                    case Native.WM_RENDERALLFORMATS:
                        log.Write("render_all_request", "");
                        break;
                    case Native.WM_DESTROYCLIPBOARD:
                        log.Write("clipboard_emptied", "");
                        break;
                }
            }
            catch (Exception error)
            {
                log.Write("owner_error", "kind=" + error.GetType().Name);
            }
            base.WndProc(ref m);
        }

        public bool Publish(int index)
        {
            if (!Open())
            {
                log.Write("publish",
                    "index=" + Fmt.Number(index) + " open=failed text_published=false");
                return false;
            }
            StringBuilder details = new StringBuilder();
            details.Append("index=").Append(Fmt.Number(index));
            details.Append(" open=ok");
            bool textPublished = false;
            try
            {
                bool emptied = Native.EmptyClipboard();
                details.Append(" emptied=").Append(Fmt.Flag(emptied));
                if (plan.EmptyOnly)
                {
                    details.Append(" formats=none");
                }
                else
                {
                    if (!plan.NoText)
                    {
                        if (plan.DelayTextMs >= 0)
                        {
                            // Delayed rendering only PROMISES the format here; the
                            // data is delivered later via WM_RENDERFORMAT. A promise
                            // is not a successful publication.
                            Native.SetClipboardData(Native.CF_UNICODETEXT, IntPtr.Zero);
                            details.Append(" text=delayed");
                        }
                        else
                        {
                            string textResult = Put(Native.CF_UNICODETEXT, TextBytes(index));
                            textPublished = textResult == "set";
                            details.Append(" text=").Append(textResult);
                        }
                    }
                    if (plan.DelaySyntheticMs >= 0)
                    {
                        Native.SetClipboardData(formatSynthetic, IntPtr.Zero);
                        details.Append(" synthetic=delayed");
                    }
                    else
                    {
                        details.Append(" synthetic=").Append(
                            Put(formatSynthetic, BitConverter.GetBytes(index)));
                    }
                    if (plan.ExcludeMonitor)
                    {
                        details.Append(" exclude_monitor=").Append(
                            Put(formatExclude, BitConverter.GetBytes(0)));
                    }
                    if (plan.History != null)
                    {
                        details.Append(" history=").Append(plan.History).Append(":").Append(
                            Put(formatHistory, FlagBytes(plan.History)));
                    }
                    if (plan.Cloud != null)
                    {
                        details.Append(" cloud=").Append(plan.Cloud).Append(":").Append(
                            Put(formatCloud, FlagBytes(plan.Cloud)));
                    }
                }
            }
            finally
            {
                Native.CloseClipboard();
            }

            if (plan.HoldAfterMs > 0)
            {
                // Re-open immediately so that a monitor reacting to the update
                // finds the clipboard busy for a controlled time.
                bool held = Native.OpenClipboard(windowHandle);
                if (held)
                {
                    Thread.Sleep(plan.HoldAfterMs);
                    Native.CloseClipboard();
                }
                details.Append(" hold_after=").Append(held ? "ok" : "failed");
            }
            details.Append(" text_published=").Append(Fmt.Flag(textPublished));
            details.Append(" seq=").Append(Fmt.Number(Native.GetClipboardSequenceNumber()));
            log.Write("publish", details.ToString());
            return true;
        }

        private void OnRenderFormat(uint format)
        {
            bool isText = format == Native.CF_UNICODETEXT;
            bool isSynthetic = format == formatSynthetic;
            string name = isText ? "text" : (isSynthetic ? "synthetic" : "other");
            log.Write("render_request", "format=" + name);
            if (!isText && !isSynthetic)
                return;
            int delay = isText ? plan.DelayTextMs : plan.DelaySyntheticMs;
            if (delay > 0)
                Thread.Sleep(delay);
            if (plan.RenderNothing)
            {
                log.Write("render_result", "format=" + name + " data=withheld");
                return;
            }
            // Inside WM_RENDERFORMAT the clipboard is already open for us.
            string result = Put(format, isText ? TextBytes(1) : BitConverter.GetBytes(1));
            log.Write("render_result", "format=" + name + " data=" + result);
        }

        private bool Open()
        {
            for (int attempt = 0; attempt < OpenAttempts; attempt++)
            {
                if (Native.OpenClipboard(windowHandle))
                    return true;
                Thread.Sleep(OpenDelayMs);
            }
            return false;
        }

        private byte[] TextBytes(int index)
        {
            string baseText = plan.CanaryId != null ? plan.CanaryId : CanaryText;
            string text = plan.Vary ? baseText + " #" + Fmt.Number(index) : baseText;
            return Encoding.Unicode.GetBytes(text + "\0");
        }

        // Builds a fresh, non-secret id for one run: the base token, a dash and
        // 16 uppercase hex characters (e.g. ...-A1B2C3D4E5F60718). Uses only a
        // random GUID: no time, user name, machine name or environment data.
        public static string MakeCanaryId()
        {
            string hex = Guid.NewGuid().ToString("N").Substring(0, 16).ToUpperInvariant();
            return CanaryBase + "-" + hex;
        }

        private static byte[] FlagBytes(string mode)
        {
            if (mode == "0")
                return BitConverter.GetBytes(0);
            if (mode == "1")
                return BitConverter.GetBytes(1);
            if (mode == "bad-value")
                return BitConverter.GetBytes(7);
            return new byte[] { 1, 0 };
        }

        private static string Put(uint format, byte[] bytes)
        {
            if (format == 0)
                return "no_format";
            IntPtr memory = Native.GlobalAlloc(
                Native.GMEM_MOVEABLE, new UIntPtr((uint)bytes.Length));
            if (memory == IntPtr.Zero)
                return "alloc_failed";
            IntPtr pointer = Native.GlobalLock(memory);
            if (pointer == IntPtr.Zero)
            {
                Native.GlobalFree(memory);
                return "lock_failed";
            }
            Marshal.Copy(bytes, 0, pointer, bytes.Length);
            Native.GlobalUnlock(memory);
            if (Native.SetClipboardData(format, memory) == IntPtr.Zero)
            {
                // Ownership stays with us only when the call fails.
                Native.GlobalFree(memory);
                return "set_failed";
            }
            return "set";
        }
    }

    internal sealed class OwnerPlan
    {
        public int Count = 1;
        public int IntervalMs;
        public bool Vary;
        public bool UniqueCanary;
        public string CanaryId;
        public bool NoText;
        public bool EmptyOnly;
        public bool ExcludeMonitor;
        public string History;
        public string Cloud;
        public int DelayTextMs = -1;
        public int DelaySyntheticMs = -1;
        public bool RenderNothing;
        public int HoldAfterMs;
        public int StaySeconds;

        public bool Delayed
        {
            get { return DelayTextMs >= 0 || DelaySyntheticMs >= 0; }
        }
    }

    internal static class OwnerProgram
    {
        private const string Usage =
            "CpbSyntheticOwner - CopyPasteBin stage 0 synthetic clipboard owner\r\n" +
            "\r\n" +
            "REPLACES the clipboard with fixed synthetic test data. It never reads\r\n" +
            "the previous clipboard content.\r\n" +
            "\r\n" +
            "Without options: one transaction with synthetic text and one synthetic\r\n" +
            "private format.\r\n" +
            "\r\n" +
            "Options:\r\n" +
            "  --count <n>               number of transactions, 1-1000 (default 1)\r\n" +
            "  --interval-ms <n>         pause between transactions, 0-60000 (default 0)\r\n" +
            "  --vary                    make every transaction's text different\r\n" +
            "  --unique-canary           use a fresh non-secret id as the test text,\r\n" +
            "                            logged as a canary_id line; the probe never\r\n" +
            "                            reads text, so it never sees the id\r\n" +
            "  --no-text                 publish only the synthetic private format\r\n" +
            "  --empty-only              only empty the clipboard\r\n" +
            "  --exclude-monitor         add ExcludeClipboardContentFromMonitorProcessing\r\n" +
            "  --history <mode>          add CanIncludeInClipboardHistory\r\n" +
            "  --cloud <mode>            add CanUploadToCloudClipboard\r\n" +
            "                            mode: 0 | 1 | bad-value | short\r\n" +
            "  --delay-text-ms <n>       delayed rendering of the text, 0-600000\r\n" +
            "  --delay-synthetic-ms <n>  delayed rendering of the synthetic format\r\n" +
            "  --render-nothing          answer render requests without data\r\n" +
            "  --hold-after-ms <n>       keep the clipboard open after publishing, 1-60000\r\n" +
            "  --stay-seconds <n>        with delayed rendering: exit after n seconds,\r\n" +
            "                            1-3600 (default: wait for Ctrl+C)\r\n" +
            "  --log <path>              also write metadata lines to a NEW file\r\n" +
            "  --help                    show this text";

        [STAThread]
        private static int Main(string[] args)
        {
            string error;
            Options options = Options.Parse(
                args,
                new string[]
                {
                    "--vary", "--no-text", "--empty-only", "--exclude-monitor",
                    "--render-nothing", "--unique-canary", "--help"
                },
                new string[]
                {
                    "--count", "--interval-ms", "--history", "--cloud",
                    "--delay-text-ms", "--delay-synthetic-ms", "--hold-after-ms",
                    "--stay-seconds", "--log"
                },
                out error);
            if (options == null)
            {
                Console.Error.WriteLine(error);
                Console.Error.WriteLine(Usage);
                return 2;
            }
            if (options.Has("--help"))
            {
                Console.Out.WriteLine(Usage);
                return 0;
            }

            OwnerPlan plan = new OwnerPlan();
            plan.Vary = options.Has("--vary");
            plan.NoText = options.Has("--no-text");
            plan.EmptyOnly = options.Has("--empty-only");
            plan.ExcludeMonitor = options.Has("--exclude-monitor");
            plan.RenderNothing = options.Has("--render-nothing");
            plan.UniqueCanary = options.Has("--unique-canary");
            if (plan.UniqueCanary)
                plan.CanaryId = OwnerWindow.MakeCanaryId();
            plan.History = options.Text("--history");
            plan.Cloud = options.Text("--cloud");
            bool valid =
                options.Number("--count", 1, 1000, 1, out plan.Count) &&
                options.Number("--interval-ms", 0, 60000, 0, out plan.IntervalMs) &&
                options.Number("--delay-text-ms", 0, 600000, -1, out plan.DelayTextMs) &&
                options.Number("--delay-synthetic-ms", 0, 600000, -1, out plan.DelaySyntheticMs) &&
                options.Number("--hold-after-ms", 1, 60000, 0, out plan.HoldAfterMs) &&
                options.Number("--stay-seconds", 1, 3600, 0, out plan.StaySeconds) &&
                ValidFlagMode(plan.History) &&
                ValidFlagMode(plan.Cloud);
            if (valid && plan.Delayed && plan.Count != 1)
                valid = false;
            if (valid && plan.NoText && plan.DelayTextMs >= 0)
                valid = false;
            if (!valid)
            {
                Console.Error.WriteLine(
                    "Invalid option value. Delayed rendering requires --count 1.");
                Console.Error.WriteLine(Usage);
                return 2;
            }

            MetadataLog log;
            try
            {
                log = new MetadataLog(options.Text("--log"));
            }
            catch (Exception)
            {
                Console.Error.WriteLine(
                    "The log file could not be created. It must not exist yet.");
                return 2;
            }

            using (log)
            {
                log.Write(
                    "owner_start",
                    "count=" + Fmt.Number(plan.Count) +
                    " delayed=" + Fmt.Flag(plan.Delayed));
                if (plan.UniqueCanary)
                    log.Write("canary_id", "value=" + plan.CanaryId);
                using (OwnerWindow window = new OwnerWindow(log, plan))
                {
                    window.Start();
                    for (int index = 1; index <= plan.Count; index++)
                    {
                        window.Publish(index);
                        if (index < plan.Count && plan.IntervalMs > 0)
                            Thread.Sleep(plan.IntervalMs);
                    }
                    if (plan.Delayed)
                    {
                        Console.CancelKeyPress += delegate(object sender, ConsoleCancelEventArgs e)
                        {
                            e.Cancel = true;
                            try
                            {
                                window.BeginInvoke(new MethodInvoker(window.Stop));
                            }
                            catch (InvalidOperationException)
                            {
                            }
                        };
                        System.Windows.Forms.Timer timer = null;
                        if (plan.StaySeconds > 0)
                        {
                            timer = new System.Windows.Forms.Timer();
                            timer.Interval = plan.StaySeconds * 1000;
                            timer.Tick += delegate(object sender, EventArgs e)
                            {
                                window.Stop();
                            };
                            timer.Start();
                        }
                        log.Write("owner_waiting", "");
                        Application.Run();
                        if (timer != null)
                            timer.Dispose();
                    }
                }
                log.Write("owner_stop", "");
            }
            return 0;
        }

        private static bool ValidFlagMode(string mode)
        {
            return mode == null || mode == "0" || mode == "1" ||
                mode == "bad-value" || mode == "short";
        }
    }
}
