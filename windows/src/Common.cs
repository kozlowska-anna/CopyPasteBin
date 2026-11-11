using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;

namespace CopyPasteBin.Stage0
{
    /// <summary>
    /// Writes one metadata line per event to the console and, optionally, to a
    /// new file. Callers pass only closed, content-free key=value tokens.
    /// </summary>
    internal sealed class MetadataLog : IDisposable
    {
        private readonly Stopwatch clock = Stopwatch.StartNew();
        private readonly object gate = new object();
        private StreamWriter file;
        private long counter;

        public MetadataLog(string path)
        {
            if (path == null)
                return;
            // CreateNew: the tools never overwrite or append to an existing file.
            FileStream stream = new FileStream(
                path, FileMode.CreateNew, FileAccess.Write, FileShare.Read);
            file = new StreamWriter(stream, new UTF8Encoding(false));
            file.AutoFlush = true;
        }

        public void Write(string type, string details)
        {
            lock (gate)
            {
                counter++;
                string line = string.Format(
                    CultureInfo.InvariantCulture,
                    "t={0:0.000} n={1} type={2}",
                    clock.Elapsed.TotalSeconds,
                    counter,
                    type);
                if (!string.IsNullOrEmpty(details))
                    line = line + " " + details;
                try
                {
                    Console.Out.WriteLine(line);
                    Console.Out.Flush();
                }
                catch (IOException)
                {
                    // The console can disappear during sign-out.
                }
                if (file != null)
                {
                    try
                    {
                        file.WriteLine(line);
                    }
                    catch (IOException)
                    {
                    }
                    catch (ObjectDisposedException)
                    {
                    }
                }
            }
        }

        public void Dispose()
        {
            lock (gate)
            {
                if (file != null)
                {
                    try
                    {
                        file.Dispose();
                    }
                    catch (IOException)
                    {
                    }
                    file = null;
                }
            }
        }
    }

    internal static class Fmt
    {
        public static string Flag(bool value)
        {
            return value ? "true" : "false";
        }

        public static string Number(long value)
        {
            return value.ToString(CultureInfo.InvariantCulture);
        }

        /// <summary>Durations are reported only as coarse ranges.</summary>
        public static string Bucket(TimeSpan elapsed)
        {
            double milliseconds = elapsed.TotalMilliseconds;
            if (milliseconds < 1)
                return "lt1ms";
            if (milliseconds < 10)
                return "1to10ms";
            if (milliseconds < 50)
                return "10to50ms";
            if (milliseconds < 250)
                return "50to250ms";
            if (milliseconds < 1000)
                return "250msto1s";
            if (milliseconds < 5000)
                return "1to5s";
            if (milliseconds < 30000)
                return "5to30s";
            return "gt30s";
        }
    }

    internal sealed class Options
    {
        private readonly Dictionary<string, string> values =
            new Dictionary<string, string>(StringComparer.Ordinal);

        public static Options Parse(
            string[] args, string[] flags, string[] valued, out string error)
        {
            Options result = new Options();
            error = null;
            for (int index = 0; index < args.Length; index++)
            {
                string name = args[index];
                if (result.values.ContainsKey(name))
                {
                    error = "Option given twice: " + name;
                    return null;
                }
                if (Array.IndexOf(flags, name) >= 0)
                {
                    result.values[name] = "";
                    continue;
                }
                if (Array.IndexOf(valued, name) >= 0)
                {
                    if (index + 1 >= args.Length)
                    {
                        error = "Missing value for " + name;
                        return null;
                    }
                    index++;
                    result.values[name] = args[index];
                    continue;
                }
                error = "Unknown option: " + name;
                return null;
            }
            return result;
        }

        public bool Has(string name)
        {
            return values.ContainsKey(name);
        }

        public string Text(string name)
        {
            string value;
            return values.TryGetValue(name, out value) ? value : null;
        }

        public bool Number(string name, int minimum, int maximum, int fallback, out int value)
        {
            value = fallback;
            string raw = Text(name);
            if (raw == null)
                return true;
            int parsed;
            if (!int.TryParse(raw, NumberStyles.None, CultureInfo.InvariantCulture, out parsed) ||
                parsed < minimum || parsed > maximum)
                return false;
            value = parsed;
            return true;
        }
    }
}
