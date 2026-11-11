using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace CopyPasteBin.Stage0
{
    /// <summary>
    /// Stage 0 clipboard metadata probe. It records that clipboard, session and
    /// power events happened. It never requests CF_UNICODETEXT, never enumerates
    /// formats and never identifies the clipboard owner.
    /// </summary>
    internal sealed class ProbeWindow : Form
    {
        private readonly MetadataLog log;
        private readonly bool presenceOnly;
        private readonly bool renderSynthetic;
        private readonly int openAttempts;
        private readonly int openDelayMs;

        private IntPtr windowHandle = IntPtr.Zero;
        private uint formatExclude;
        private uint formatHistory;
        private uint formatCloud;
        private uint formatSynthetic;
        private uint ownSession;
        private bool ownSessionKnown;
        private bool listenerRegistered;
        private bool sessionRegistered;
        private bool locked;
        private bool stopped;
        private long updates;
        private long gatedUpdates;
        private long failedOpens;
        private long foreignSessionEvents;

        public ProbeWindow(
            MetadataLog log,
            bool presenceOnly,
            bool renderSynthetic,
            int openAttempts,
            int openDelayMs)
        {
            this.log = log;
            this.presenceOnly = presenceOnly;
            this.renderSynthetic = renderSynthetic;
            this.openAttempts = openAttempts;
            this.openDelayMs = openDelayMs;
        }

        /// <summary>Creates the hidden top-level window without showing it.</summary>
        public void Start()
        {
            IntPtr created = Handle;
            if (created == IntPtr.Zero)
                log.Write("probe_error", "kind=no_window");
        }

        public void Stop()
        {
            if (stopped)
                return;
            stopped = true;
            log.Write(
                "probe_summary",
                "clipboard_updates=" + Fmt.Number(updates) +
                " gated_updates=" + Fmt.Number(gatedUpdates) +
                " failed_opens=" + Fmt.Number(failedOpens) +
                " other_session_events_ignored=" + Fmt.Number(foreignSessionEvents));
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

            uint session;
            ownSessionKnown = Native.ProcessIdToSessionId(
                Native.GetCurrentProcessId(), out session);
            ownSession = session;

            listenerRegistered = Native.AddClipboardFormatListener(windowHandle);
            int listenerError = listenerRegistered ? 0 : Marshal.GetLastWin32Error();
            log.Write(
                "listener_registration",
                "ok=" + Fmt.Flag(listenerRegistered) +
                " error=" + Fmt.Number(listenerError) +
                " seq=" + Fmt.Number(Native.GetClipboardSequenceNumber()));

            sessionRegistered = Native.WTSRegisterSessionNotification(
                windowHandle, Native.NOTIFY_FOR_THIS_SESSION);
            int sessionError = sessionRegistered ? 0 : Marshal.GetLastWin32Error();
            log.Write(
                "session_registration",
                "ok=" + Fmt.Flag(sessionRegistered) +
                " error=" + Fmt.Number(sessionError) +
                " own_session_known=" + Fmt.Flag(ownSessionKnown));
        }

        protected override void OnHandleDestroyed(EventArgs e)
        {
            if (listenerRegistered)
            {
                bool removed = Native.RemoveClipboardFormatListener(windowHandle);
                listenerRegistered = false;
                log.Write("listener_removed", "ok=" + Fmt.Flag(removed));
            }
            if (sessionRegistered)
            {
                Native.WTSUnRegisterSessionNotification(windowHandle);
                sessionRegistered = false;
            }
            base.OnHandleDestroyed(e);
        }

        protected override void WndProc(ref Message m)
        {
            try
            {
                switch (m.Msg)
                {
                    case Native.WM_CLIPBOARDUPDATE:
                        OnClipboardUpdate();
                        break;
                    case Native.WM_WTSSESSION_CHANGE:
                        OnSessionChange(m.WParam.ToInt64(), m.LParam.ToInt64());
                        break;
                    case Native.WM_POWERBROADCAST:
                        log.Write("power", "event=" + PowerName(m.WParam.ToInt64()));
                        break;
                    case Native.WM_QUERYENDSESSION:
                        log.Write("query_end_session", EndSessionFlags(m.LParam.ToInt64()));
                        break;
                    case Native.WM_ENDSESSION:
                        log.Write(
                            "end_session",
                            "ending=" + Fmt.Flag(m.WParam != IntPtr.Zero) +
                            " " + EndSessionFlags(m.LParam.ToInt64()));
                        break;
                }
            }
            catch (Exception error)
            {
                // Only the exception type is reported. No message text.
                log.Write("probe_error", "kind=" + error.GetType().Name);
            }
            base.WndProc(ref m);
        }

        private void OnClipboardUpdate()
        {
            updates++;
            StringBuilder details = new StringBuilder();
            details.Append("seq_before=");
            details.Append(Fmt.Number(Native.GetClipboardSequenceNumber()));

            if (locked)
            {
                // While the session is locked the probe does not open the
                // clipboard and does not query any format.
                gatedUpdates++;
                details.Append(" gate=locked");
                log.Write("clipboard_update", details.ToString());
                return;
            }
            details.Append(" gate=open");

            // IsClipboardFormatAvailable neither opens the clipboard nor asks
            // the owner to render anything.
            bool text = Native.IsClipboardFormatAvailable(Native.CF_UNICODETEXT);
            string exclude = Presence(formatExclude);
            string history = Presence(formatHistory);
            string cloud = Presence(formatCloud);
            string synthetic = Presence(formatSynthetic);
            details.Append(" text=").Append(Fmt.Flag(text));
            details.Append(" exclude_monitor=").Append(exclude);
            details.Append(" history_fmt=").Append(history);
            details.Append(" cloud_fmt=").Append(cloud);
            details.Append(" synthetic_fmt=").Append(synthetic);

            string historyValue = "-";
            string cloudValue = "-";
            string render = "-";
            int attempts = 0;
            int openError = 0;
            bool opened = false;
            Stopwatch openClock = Stopwatch.StartNew();
            while (attempts < openAttempts)
            {
                attempts++;
                opened = Native.OpenClipboard(windowHandle);
                if (opened)
                    break;
                openError = Marshal.GetLastWin32Error();
                if (attempts < openAttempts)
                    Thread.Sleep(openDelayMs);
            }
            openClock.Stop();
            if (opened)
                openError = 0;
            else
                failedOpens++;

            details.Append(" open=").Append(opened ? "ok" : "failed");
            details.Append(" open_error=").Append(Fmt.Number(openError));
            details.Append(" open_attempts=").Append(Fmt.Number(attempts));
            details.Append(" open_time=").Append(Fmt.Bucket(openClock.Elapsed));

            if (opened)
            {
                try
                {
                    if (!presenceOnly)
                    {
                        if (history == "present")
                            historyValue = ReadPrivacyFlag(formatHistory);
                        if (cloud == "present")
                            cloudValue = ReadPrivacyFlag(formatCloud);
                    }
                    if (renderSynthetic && synthetic == "present")
                        render = RequestSyntheticFormat();
                }
                finally
                {
                    Native.CloseClipboard();
                }
            }

            details.Append(" history_val=").Append(historyValue);
            details.Append(" cloud_val=").Append(cloudValue);
            details.Append(" synthetic_render=").Append(render);
            details.Append(" seq_after=");
            details.Append(Fmt.Number(Native.GetClipboardSequenceNumber()));
            log.Write("clipboard_update", details.ToString());
        }

        private static string Presence(uint format)
        {
            if (format == 0)
                return "unknown";
            return Native.IsClipboardFormatAvailable(format) ? "present" : "absent";
        }

        /// <summary>
        /// Reads one of the two documented DWORD privacy flags. The result is a
        /// closed token; an unexpected value is never printed.
        /// </summary>
        private static string ReadPrivacyFlag(uint format)
        {
            IntPtr memory = Native.GetClipboardData(format);
            if (memory == IntPtr.Zero)
                return "invalid_no_data";
            ulong size = Native.GlobalSize(memory).ToUInt64();
            if (size < 4)
                return "invalid_short";
            IntPtr pointer = Native.GlobalLock(memory);
            if (pointer == IntPtr.Zero)
                return "invalid_lock";
            int value;
            try
            {
                value = Marshal.ReadInt32(pointer);
            }
            finally
            {
                Native.GlobalUnlock(memory);
            }
            string suffix = size == 4 ? "" : "_size_gt4";
            if (value == 0)
                return "0" + suffix;
            if (value == 1)
                return "1" + suffix;
            return "invalid_value" + suffix;
        }

        /// <summary>
        /// Opt-in (--render-synthetic). Asks only for the stage 0 synthetic
        /// format published by CpbSyntheticOwner, to measure how long delayed
        /// rendering blocks the caller. The returned memory is never locked,
        /// measured or read.
        /// </summary>
        private string RequestSyntheticFormat()
        {
            Stopwatch clock = Stopwatch.StartNew();
            IntPtr memory = Native.GetClipboardData(formatSynthetic);
            int error = memory == IntPtr.Zero ? Marshal.GetLastWin32Error() : 0;
            clock.Stop();
            return (memory == IntPtr.Zero ? "null" : "ok") +
                ",error:" + Fmt.Number(error) +
                ",time:" + Fmt.Bucket(clock.Elapsed);
        }

        private void OnSessionChange(long code, long session)
        {
            if (ownSessionKnown && session != ownSession)
            {
                foreignSessionEvents++;
                return;
            }
            if (code == 7)
                locked = true;
            else if (code == 8)
                locked = false;
            log.Write(
                "session",
                "event=" + SessionName(code) +
                " own_session_verified=" + Fmt.Flag(ownSessionKnown) +
                " gate=" + (locked ? "locked" : "open"));
        }

        private static string SessionName(long code)
        {
            switch (code)
            {
                case 1: return "console_connect";
                case 2: return "console_disconnect";
                case 3: return "remote_connect";
                case 4: return "remote_disconnect";
                case 5: return "logon";
                case 6: return "logoff";
                case 7: return "lock";
                case 8: return "unlock";
                case 9: return "remote_control";
                case 10: return "create";
                case 11: return "terminate";
                default: return "other";
            }
        }

        private static string PowerName(long code)
        {
            switch (code)
            {
                case 4: return "suspend";
                case 7: return "resume_suspend";
                case 10: return "power_status_change";
                case 18: return "resume_automatic";
                case 32787: return "power_setting_change";
                default: return "other";
            }
        }

        private static string EndSessionFlags(long flags)
        {
            return "logoff=" + Fmt.Flag((flags & 0x80000000L) != 0) +
                " critical=" + Fmt.Flag((flags & 0x40000000L) != 0) +
                " close_app=" + Fmt.Flag((flags & 0x1L) != 0);
        }
    }

    internal static class ProbeProgram
    {
        private const string Usage =
            "CpbClipboardProbe - CopyPasteBin stage 0 clipboard metadata probe\r\n" +
            "\r\n" +
            "Records clipboard, session and power events as metadata only.\r\n" +
            "It never reads clipboard text and never identifies other programs.\r\n" +
            "\r\n" +
            "Options:\r\n" +
            "  --log <path>           also write the metadata lines to a NEW file\r\n" +
            "  --presence-only        do not read the two DWORD privacy flag values\r\n" +
            "  --render-synthetic     request the stage 0 synthetic format (never text)\r\n" +
            "                         to time delayed rendering; data is not read\r\n" +
            "  --open-attempts <n>    OpenClipboard attempts per event, 1-20 (default 1)\r\n" +
            "  --open-delay-ms <n>    pause between attempts, 1-500 (default 25)\r\n" +
            "  --help                 show this text\r\n" +
            "\r\n" +
            "Stop with Ctrl+C.";

        [STAThread]
        private static int Main(string[] args)
        {
            string error;
            Options options = Options.Parse(
                args,
                new string[] { "--presence-only", "--render-synthetic", "--help" },
                new string[] { "--log", "--open-attempts", "--open-delay-ms" },
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
            int openAttempts;
            int openDelayMs;
            if (!options.Number("--open-attempts", 1, 20, 1, out openAttempts) ||
                !options.Number("--open-delay-ms", 1, 500, 25, out openDelayMs))
            {
                Console.Error.WriteLine("Invalid numeric option.");
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
                bool presenceOnly = options.Has("--presence-only");
                bool renderSynthetic = options.Has("--render-synthetic");
                log.Write(
                    "probe_start",
                    "probe_version=0.1" +
                    " elevated=" + ElevatedState() +
                    " presence_only=" + Fmt.Flag(presenceOnly) +
                    " render_synthetic=" + Fmt.Flag(renderSynthetic) +
                    " open_attempts=" + Fmt.Number(openAttempts) +
                    " open_delay_ms=" + Fmt.Number(openDelayMs));

                using (ProbeWindow window = new ProbeWindow(
                    log, presenceOnly, renderSynthetic, openAttempts, openDelayMs))
                {
                    window.Start();
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
                    Application.Run();
                }
                log.Write("probe_stop", "");
            }
            return 0;
        }

        private static string ElevatedState()
        {
            try
            {
                using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
                {
                    WindowsPrincipal principal = new WindowsPrincipal(identity);
                    return Fmt.Flag(principal.IsInRole(WindowsBuiltInRole.Administrator));
                }
            }
            catch (Exception)
            {
                return "unknown";
            }
        }
    }
}
