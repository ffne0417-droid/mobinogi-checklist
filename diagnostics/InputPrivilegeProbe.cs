using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
class InputPrivilegeProbe {
 [DllImport("kernel32.dll",SetLastError=true)]static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
 [DllImport("advapi32.dll",SetLastError=true)]static extern bool OpenProcessToken(IntPtr p,uint access,out IntPtr token);
 [DllImport("advapi32.dll",SetLastError=true)]static extern bool GetTokenInformation(IntPtr token,int cls,IntPtr data,int len,out int needed);
 [DllImport("kernel32.dll")]static extern bool CloseHandle(IntPtr h);
 static void Main(){foreach(string name in new[]{"MabinogiMobile","MouseInputMonitorV2","ClickChatTest","key_macro"})foreach(Process p in Process.GetProcessesByName(name)){
  IntPtr process=OpenProcess(0x1000,false,p.Id),token=IntPtr.Zero;string result="unknown";
  if(process==IntPtr.Zero)result="OpenProcess denied error="+Marshal.GetLastWin32Error();
  else if(!OpenProcessToken(process,8,out token))result="OpenProcessToken denied error="+Marshal.GetLastWin32Error();
  else{IntPtr data=Marshal.AllocHGlobal(4);try{int needed;if(GetTokenInformation(token,20,data,4,out needed))result="elevated="+(Marshal.ReadInt32(data)!=0);else result="GetTokenInformation error="+Marshal.GetLastWin32Error();}finally{Marshal.FreeHGlobal(data);}}
  Console.WriteLine(name+" pid="+p.Id+" session="+p.SessionId+" "+result);if(token!=IntPtr.Zero)CloseHandle(token);if(process!=IntPtr.Zero)CloseHandle(process);p.Dispose();
 }}
}
