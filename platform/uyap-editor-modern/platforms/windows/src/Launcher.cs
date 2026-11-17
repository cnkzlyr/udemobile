using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace UYAPLauncher
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
                
                // 1. Java 14.0.2 calistirilabilir dosya tespiti
                string javaCmd = Path.Combine(baseDir, @"jdk-14.0.2\bin\javaw.exe");
                if (!File.Exists(javaCmd))
                {
                    string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                    string altJava = Path.Combine(localAppData, @"Programs\UYAP Editor Modern\jdk-14.0.2\bin\javaw.exe");
                    if (File.Exists(altJava))
                    {
                        javaCmd = altJava;
                    }
                    else
                    {
                        altJava = Path.Combine(localAppData, @"UYAPEditorModern\jdk-14.0.2\bin\javaw.exe");
                        if (File.Exists(altJava))
                        {
                            javaCmd = altJava;
                        }
                        else
                        {
                            string javaHome = Environment.GetEnvironmentVariable("JAVA_HOME");
                            if (!string.IsNullOrEmpty(javaHome) && File.Exists(Path.Combine(javaHome, @"bin\javaw.exe")))
                            {
                                javaCmd = Path.Combine(javaHome, @"bin\javaw.exe");
                            }
                            else
                            {
                                javaCmd = "javaw.exe";
                            }
                        }
                    }
                }

                // 2. Modernizer ve E-Imza Agent
                string modernizerJar = Path.Combine(baseDir, "uyap-modernizer.jar");
                string pcscJar = Path.Combine(baseDir, "uyap-pcsc-agent.jar");
                StringBuilder agentOpts = new StringBuilder();
                if (File.Exists(modernizerJar))
                {
                    agentOpts.AppendFormat("-javaagent:\"{0}\" ", modernizerJar);
                }
                if (File.Exists(pcscJar))
                {
                    agentOpts.AppendFormat("-javaagent:\"{0}\" ", pcscJar);
                }

                // 3. Classpath ve Resmi UYAP Kutuphaneleri
                string cpOpt;
                string editorLib = Path.Combine(baseDir, "editor_lib.jar");
                if (File.Exists(editorLib))
                {
                    cpOpt = string.Format("-cp \"{0}\\uyap-modernizer.jar;{0}\\*\"", baseDir);
                }
                else
                {
                    string[] candidateDirs = new string[] {
                        @"C:\Uyap\Uyap Kelime Islemci",
                        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), @"UYAP\UYAPEditor"),
                        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), @"UYAP\UYAPEditor"),
                        @"C:\UYAPEditor",
                        @"C:\Program Files\Uyap Kelime Islemci",
                        @"C:\Program Files (x86)\Uyap Kelime Islemci"
                    };
                    string foundDir = null;
                    foreach (string d in candidateDirs)
                    {
                        if (Directory.Exists(d) && File.Exists(Path.Combine(d, "editor_lib.jar")))
                        {
                            foundDir = d;
                            break;
                        }
                    }
                    if (foundDir != null)
                    {
                        cpOpt = string.Format("-cp \"{0}\\uyap-modernizer.jar;{0}\\*;{1}\\*\"", baseDir, foundDir);
                    }
                    else
                    {
                        MessageBox.Show(
                            "Resmi UYAP kütüphaneleri (editor_lib.jar) bulunamadı!\n\n" +
                            "Lütfen 'install.ps1' kurulum betiğini çalıştırın veya resmi UYAP Editör'ü kurun.",
                            "UYAP Editör Modern",
                            MessageBoxButtons.OK,
                            MessageBoxIcon.Warning
                        );
                        return;
                    }
                }

                // 4. E-Imza & Akilli Kart (Windows akisp11.dll & ArkSigner)
                string sysRoot = Environment.GetEnvironmentVariable("SystemRoot");
                if (string.IsNullOrEmpty(sysRoot)) sysRoot = @"C:\Windows";
                string pkcs11Opts = string.Format("-Djava.library.path=\"{0};{1}\\System32;{1}\\SysWOW64\"", baseDir, sysRoot);

                // 5. UI ve Performans Parametreleri
                string fontOpts = "-Dawt.useSystemAAFontSettings=lcd -Dswing.aatext=true";
                string memOpts = "-Xms256m -Xmx1024m -XX:+UseG1GC -XX:+UseStringDeduplication";

                // 6. Profil ve Ayarlar (.uki)
                string userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
                string ukiDir = Path.Combine(userProfile, ".uki");
                if (!Directory.Exists(ukiDir))
                {
                    try { Directory.CreateDirectory(ukiDir); } catch {}
                }
                string modPropSrc = Path.Combine(baseDir, "modernizer.properties");
                string modPropDst = Path.Combine(ukiDir, "modernizer.properties");
                if (File.Exists(modPropSrc) && !File.Exists(modPropDst))
                {
                    try { File.Copy(modPropSrc, modPropDst); } catch {}
                }

                // 7. Baslangic Modu (Dokuman / Sablon)
                #if TEMPLATE_MODE
                string editorType = "EDITOR_TYPE_TEMPLATE";
                #else
                string editorType = "EDITOR_TYPE_DOCUMENT";
                #endif

                // 8. Komut satiri argumanlarini olustur
                StringBuilder sb = new StringBuilder();
                sb.Append(pkcs11Opts).Append(" ");
                sb.Append(memOpts).Append(" ");
                sb.Append(fontOpts).Append(" ");
                if (agentOpts.Length > 0)
                {
                    sb.Append(agentOpts.ToString());
                }
                sb.Append(cpOpt).Append(" ");
                sb.Append("tr.com.havelsan.uyap.system.editor.common.WPAppManager ");
                sb.Append("\"getNewWPInstance\" ");

                if (args.Length > 0 && !string.IsNullOrEmpty(args[0]))
                {
                    string target = args[0].Trim('\"');
                    if (target.EndsWith(".usf", StringComparison.OrdinalIgnoreCase))
                    {
                        editorType = "EDITOR_TYPE_TEMPLATE";
                    }
                    else if (target.EndsWith(".udf", StringComparison.OrdinalIgnoreCase))
                    {
                        editorType = "EDITOR_TYPE_DOCUMENT";
                    }
                    sb.Append("\"").Append(editorType).Append("\" ");
                    sb.Append("\"").Append(target).Append("\"");
                }
                else
                {
                    sb.Append("\"").Append(editorType).Append("\"");
                }

                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = javaCmd;
                psi.Arguments = sb.ToString();
                psi.WorkingDirectory = baseDir;
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;

                Process.Start(psi);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "UYAP Editör Modern başlatılamadı:\n\n" + ex.Message,
                    "UYAP Editör Modern",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }
    }
}
