using System;
using System.Threading;

namespace CopyPasteBin.Stage0
{
    /// <summary>
    /// Stage 0 clipboard blocker. It opens the clipboard, keeps it open for a
    /// controlled time and closes it. It never reads, empties or writes data.
    /// </summary>
    internal static class BlockerProgram
    {
        private const string Usage =
            "CpbClipboardBlocker - CopyPasteBin stage 0 clipboard blocker\r\n" +
            "\r\n" +
            "Keeps the clipboard open so that other programs cannot open it.\r\n" +
            "It never reads or changes the clipboard content.\r\n" +
            "\r\n" +
            "Options:\r\n" +
            "  --hold-ms <n>    how long to keep the clipboard open, 1-60000 (default 1000)\r\n" +
            "  --count <n>      number of holds, 1-10000 (default 1)\r\n" +
            "  --pause-ms <n>   pause between holds, 1-60000 (default 20)\r\n" +
            "  --log <path>     also write metadata lines to a NEW file\r\n" +
            "  --help           show this text\r\n" +
            "\r\n" +
            "Ctrl+C ends the program; Windows then releases the clipboard.";

        private const int OpenAttempts = 400;
        private const int OpenDelayMs = 5;

        private static int Main(string[] args)
        {
            string error;
            Options options = Options.Parse(
                args,
                new string[] { "--help" },
                new string[] { "--hold-ms", "--count", "--pause-ms", "--log" },
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
            int holdMs;
            int count;
            int pauseMs;
            if (!options.Number("--hold-ms", 1, 60000, 1000, out holdMs) ||
                !options.Number("--count", 1, 10000, 1, out count) ||
                !options.Number("--pause-ms", 1, 60000, 20, out pauseMs))
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
                log.Write(
                    "blocker_start",
                    "hold_ms=" + Fmt.Number(holdMs) +
                    " count=" + Fmt.Number(count) +
                    " pause_ms=" + Fmt.Number(pauseMs));
                for (int index = 1; index <= count; index++)
                {
                    bool opened = false;
                    for (int attempt = 0; attempt < OpenAttempts && !opened; attempt++)
                    {
                        opened = Native.OpenClipboard(IntPtr.Zero);
                        if (!opened)
                            Thread.Sleep(OpenDelayMs);
                    }
                    if (!opened)
                    {
                        log.Write("hold", "index=" + Fmt.Number(index) + " open=failed");
                    }
                    else
                    {
                        log.Write("hold_start", "index=" + Fmt.Number(index));
                        try
                        {
                            Thread.Sleep(holdMs);
                        }
                        finally
                        {
                            Native.CloseClipboard();
                        }
                        log.Write("hold_end", "index=" + Fmt.Number(index));
                    }
                    if (index < count)
                        Thread.Sleep(pauseMs);
                }
                log.Write("blocker_stop", "");
            }
            return 0;
        }
    }
}
