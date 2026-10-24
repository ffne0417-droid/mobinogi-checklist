using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

// Mouse-only observation. No keyboard hook or synthetic input.
class MouseInputMonitor : Form {
 [StructLayout(LayoutKind.Sequential)]struct POINT{public int X,Y;}
 [StructLayout(LayoutKind.Sequential)]struct DATA{public POINT pt;public uint mouseData,flags,time;public UIntPtr extra;}
 delegate IntPtr HookProc(int code,IntPtr message,IntPtr data);
 [DllImport("user32.dll",SetLastError=true)]static extern IntPtr SetWindowsHookEx(int id,HookProc proc,IntPtr module,uint thread);
 [DllImport("user32.dll")]static extern bool UnhookWindowsHookEx(IntPtr hook);
 [DllImport("user32.dll")]static extern IntPtr CallNextHookEx(IntPtr hook,int code,IntPtr message,IntPtr data);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)]static extern IntPtr GetModuleHandle(string name);
 [DllImport("user32.dll")]static extern bool GetCursorPos(out POINT point);
 [DllImport("user32.dll")]static extern bool ScreenToClient(IntPtr hwnd,ref POINT point);
 [DllImport("user32.dll")]static extern bool GetClientRect(IntPtr hwnd,out RECT rect);
 [DllImport("user32.dll")]static extern bool ClientToScreen(IntPtr hwnd,ref POINT point);
 [DllImport("user32.dll")]static extern IntPtr WindowFromPoint(POINT point);
 [DllImport("user32.dll")]static extern IntPtr GetAncestor(IntPtr hwnd,uint flags);
 [DllImport("user32.dll")]static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")]static extern uint GetDpiForWindow(IntPtr hwnd);
 [StructLayout(LayoutKind.Sequential)]struct RECT{public int L,T,R,B;}
 [DllImport("user32.dll")]static extern bool SetProcessDPIAware();
 readonly Label position=new Label{Dock=DockStyle.Top,Height=70};
 readonly ListBox events=new ListBox{Dock=DockStyle.Fill,HorizontalScrollbar=true};
 readonly ConcurrentQueue<string> pending=new ConcurrentQueue<string>();
 readonly System.Windows.Forms.Timer timer=new System.Windows.Forms.Timer{Interval=50};
 readonly string log=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"mouse-input-monitor-v2.log");
 HookProc callback;IntPtr hook,game;int ticks;bool watching=true;DateTime expires=DateTime.Now.AddMinutes(10);
 void FindGame(){game=IntPtr.Zero;foreach(Process p in Process.GetProcessesByName("MabinogiMobile")){try{if(p.MainWindowHandle!=IntPtr.Zero){game=p.MainWindowHandle;break;}}finally{p.Dispose();}}}
 string Coordinates(POINT pt){string text="screen="+pt.X+","+pt.Y;if(game!=IntPtr.Zero){POINT cp=pt;RECT r;if(ScreenToClient(game,ref cp)&&GetClientRect(game,out r))text+=" gameClient="+cp.X+","+cp.Y+" inside="+(cp.X>=0&&cp.Y>=0&&cp.X<r.R&&cp.Y<r.B);}return text;}
 string ClickContext(POINT pt){
  IntPtr hit=GetAncestor(WindowFromPoint(pt),2),fg=GetForegroundWindow();
  POINT cursor;bool got=GetCursorPos(out cursor);
  string text=" hitRoot="+hit+" foreground="+fg+" game="+game+" targetGame="+(game!=IntPtr.Zero&&hit==game)+" cursorNow="+(got?cursor.X+","+cursor.Y:"unavailable");
  if(game!=IntPtr.Zero){POINT cp=pt,origin=new POINT();RECT r;
   if(ScreenToClient(game,ref cp)&&ClientToScreen(game,ref origin)&&GetClientRect(game,out r)){
    bool inside=cp.X>=0&&cp.Y>=0&&cp.X<r.R&&cp.Y<r.B;
    text+=" gameClient="+cp.X+","+cp.Y+" clientOrigin="+origin.X+","+origin.Y+" clientSize="+r.R+","+r.B+" inside="+inside;
    if(inside&&r.R>0&&r.B>0)text+=" relative="+((double)cp.X/r.R).ToString("F6",System.Globalization.CultureInfo.InvariantCulture)+","+((double)cp.Y/r.B).ToString("F6",System.Globalization.CultureInfo.InvariantCulture);
   }
   try{text+=" dpi="+GetDpiForWindow(game);}catch(EntryPointNotFoundException){text+=" dpi=unsupported";}
  }
  return text;
 }
 IntPtr Observe(int code,IntPtr message,IntPtr data){
  if(code>=0&&watching){int m=message.ToInt32();string kind=null;
   switch(m){case 0x201:kind="LEFT_DOWN";break;case 0x202:kind="LEFT_UP";break;case 0x204:kind="RIGHT_DOWN";break;case 0x205:kind="RIGHT_UP";break;case 0x207:kind="MIDDLE_DOWN";break;case 0x208:kind="MIDDLE_UP";break;}
   if(kind!=null){DATA d=(DATA)Marshal.PtrToStructure(data,typeof(DATA));pending.Enqueue(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff")+" "+kind+" screen="+d.pt.X+","+d.pt.Y+" injected="+((d.flags&1)!=0)+" lowerIntegrity="+((d.flags&2)!=0)+ClickContext(d.pt));}
  }
  return CallNextHookEx(hook,code,message,data);
 }
 void Flush(){string row;while(pending.TryDequeue(out row)){events.Items.Insert(0,row);if(events.Items.Count>250)events.Items.RemoveAt(250);try{File.AppendAllText(log,row+Environment.NewLine);}catch{position.Text="로그 저장 실패 — 화면 관찰은 계속됩니다.";}}}
 void StopWatch(){watching=false;if(hook!=IntPtr.Zero){UnhookWindowsHookEx(hook);hook=IntPtr.Zero;}Flush();}
 MouseInputMonitor(){
  Text="마우스 입력 관찰 v2 · 대상 창/게임 좌표 기록";Size=new Size(900,390);StartPosition=FormStartPosition.CenterScreen;
  position.Font=new Font("Malgun Gothic",11);position.Text="좌표 확인 중…";
  var info=new Label{Dock=DockStyle.Bottom,Height=50,Text="키보드·화면·채팅 내용은 기록하지 않습니다. 클릭 위치/시각만 로컬 로그에 저장합니다.\n10분 후 관찰을 자동 종료합니다. 창을 닫아도 즉시 종료됩니다."};
  var stop=new Button{Dock=DockStyle.Bottom,Height=36,Text="관찰 중지"};stop.Click+=(s,e)=>{StopWatch();stop.Enabled=false;position.Text="관찰 중지됨 — 창을 닫아 종료하세요.";};
  Controls.Add(events);Controls.Add(position);Controls.Add(stop);Controls.Add(info);
  callback=Observe;hook=SetWindowsHookEx(14,callback,GetModuleHandle(null),0);
  if(hook==IntPtr.Zero)throw new Exception("마우스 관찰 등록 실패: "+Marshal.GetLastWin32Error());
  FindGame();pending.Enqueue(DateTime.Now.ToString("s")+" SESSION_START v2 game="+game);timer.Tick+=(s,e)=>{Flush();if(!watching)return;if(DateTime.Now>=expires){StopWatch();position.Text="10분 관찰 완료 — 입력 관찰이 종료됐습니다.";return;}if(++ticks%40==0)FindGame();POINT p;if(GetCursorPos(out p))position.Text=Coordinates(p)+"\n남은 관찰 "+Math.Ceiling((expires-DateTime.Now).TotalSeconds)+"초 · 최근 클릭은 아래에 표시";};timer.Start();
  FormClosed+=(s,e)=>{timer.Stop();StopWatch();};
 }
 [STAThread]static void Main(){SetProcessDPIAware();Application.EnableVisualStyles();try{Application.Run(new MouseInputMonitor());}catch(Exception e){MessageBox.Show(e.Message,"관찰 도구 오류");}}
}
