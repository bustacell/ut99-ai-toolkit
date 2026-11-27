//=============================================================================
// DDConsole - Demo Director console.
// Extends the stock UTConsole (XConsole refuses to be subclassed), adds:
//  * every console message / kill message is written to the log with demo time
//  * a client-side DDWatcher actor that logs playback state ~4x per second
//  * exec commands DDStatus / DDPlayers / DDMark for automation feedback
// All output lines look like:  DemoDirector: DD|<TAG>|t=<demo seconds>|...
//=============================================================================
class DDConsole extends UTConsole config;

var DDWatcher Watcher;
var bool bCleanHud;     // true when HudMode == 2 (kept for older code paths)
var int HudMode;        // 0 = original HUD, 1 = cinematic HUD (DDCineHUD), 2 = blank (DDBlankHUD), 3 = DDCineHUD without messages
var string TagIds;      // " 3 7 " = PlayerIDs that get a name tag in free-cam shots
var bool bAutoClose;    // ddautoclose 1: close any UWindow a demo opens (server rules browser, vote windows);
                        // an open window swallows the ScrollLock command channel

// ddtype: cosmetic console typing (drop the console, type text, "enter", slide up). Real-time clock.
var int TypeState;      // 0 off, 1 waiting for demo time TypeDT0, 2 running
var string TypeText;
var float TypeDT0, TypeClock, TypeCps, TypeHold, TypeDrop;
var string EnteredStr;  // the "entered" line shown while the console slides back up
var Font TypeFont;      // LadderFonts.UTLadder30 (has lowercase; Canvas.LargeFont does not)

function DemoInterface GetDriver()
{
	if (Viewport != None && DemoPlaybackSpec(Viewport.Actor) != None)
		return DemoPlaybackSpec(Viewport.Actor).Driver;
	return None;
}

function string DemoTimeStr()
{
	local DemoInterface D;
	D = GetDriver();
	if (D == None)
		return "t=-1";
	return "t=" $ D.GetCurrentTime();
}

function DDLog(string Tag, string Text)
{
	Log("DD|" $ Tag $ "|" $ DemoTimeStr() $ "|" $ Text, 'DemoDirector');
}

function EnsureWatcher()
{
	if (Viewport == None || Viewport.Actor == None)
		return;
	if (Watcher != None && !Watcher.bDeleteMe && Watcher.Level == Viewport.Actor.Level)
		return;
	if (DemoPlaybackSpec(Viewport.Actor) == None)
		return;
	Watcher = Viewport.Actor.Spawn(class'DDWatcher');
	if (Watcher != None)
	{
		Watcher.Con = self;
		DDLog("WATCHER", "spawned map=" $ Viewport.Actor.Level.Title $ "|file=" $ Viewport.Actor.Level.GetURLMap());
	}
}

event Message(PlayerReplicationInfo PRI, coerce string Msg, name N)
{
	local string Who;
	if (PRI != None)
		Who = PRI.PlayerName;
	if (Msg != "")
		DDLog("MSG", "type=" $ N $ "|from=" $ Who $ "|" $ Msg);
	if (TypeState == 0 && EnteredStr == "")   // keep names out of the ddtype console
		Super.Message(PRI, Msg, N);
	EnsureWatcher();
}

event AddString(coerce string Msg)
{
	if (Msg != "")
		DDLog("STR", Msg);
	if (TypeState == 0 && EnteredStr == "")
		Super.AddString(Msg);
	EnsureWatcher();
}

event Tick(float Delta)
{
	Super.Tick(Delta);
	EnsureWatcher();
	if (TypeState > 0)
		TickType(Delta);
	else if (EnteredStr != "" && ConsolePos <= 0)
		EnteredStr = "";
}

// ddtype view: only our prompt (and the entered line), large font, console green.
simulated function DrawConsoleView(Canvas C)
{
	local float XL, YL, Y;
	if (TypeState == 0 && EnteredStr == "")
	{
		Super.DrawConsoleView(C);
		return;
	}
	if (TypeFont == None)
		TypeFont = Font(DynamicLoadObject("LadderFonts.UTLadder36", class'Font'));
	if (TypeFont != None)
		C.Font = TypeFont;
	else
		C.Font = C.MedFont;
	C.Style = 1;
	C.DrawColor.R = 120; C.DrawColor.G = 255; C.DrawColor.B = 120;
	C.StrLen("(>", XL, YL);
	Y = ConsoleLines - YL * 1.5;
	if (EnteredStr != "")
	{
		C.SetPos(24, Y - YL * 1.2);
		C.DrawText(EnteredStr, false);
	}
	C.SetPos(24, Y);
	C.DrawText("(>" @ TypedStr, false);
}

// Timeline (wall seconds after demo time reaches dt0): console drops (TypeDrop), text types at TypeCps chars/s,
// cursor blinks for TypeHold, then the line is "entered" (moves into the history) and the console slides up.
function TickType(float Delta)
{
	local float TType, TEnter;
	local int N;
	if (TypeState == 1)
	{
		if (Watcher == None || Watcher.DemoTime() < TypeDT0)
			return;
		TypeState = 2;
		TypeClock = 0;
		ClearMessages();
		TypedStr = "";
		EnteredStr = "";
		ConsoleDest = 0.33;
		DDLog("TYPE", "drop");
		return;
	}
	TypeClock += Delta;
	TType = TypeDrop;
	TEnter = TType + Len(TypeText) / FMax(TypeCps, 1) + TypeHold;
	if (TypeClock < TEnter)
	{
		N = Clamp(int((TypeClock - TType) * TypeCps), 0, Len(TypeText));
		TypedStr = Left(TypeText, N);
		if (int(TypeClock * 3) % 2 == 0)
			TypedStr = TypedStr $ "_";
		return;
	}
	EnteredStr = "(>" @ TypeText;
	TypedStr = "";
	ConsoleDest = 0.0;
	TypeState = 0;
	DDLog("TYPE", "enter|text=" $ TypeText);
}

// "ddtype dt0=58.1 cps=9 hold=0.6 drop=0.7 text=slomo 0"   (text = rest of the line); "ddtype off"
exec function DDType(string Args)
{
	local int i;
	if (Args == "" || Args ~= "off")
	{
		TypeState = 0;
		TypedStr = "";
		ConsoleDest = 0.0;
		return;
	}
	i = InStr(Args, "text=");
	if (i < 0)
		return;
	TypeText = Mid(Args, i + 5);
	Args = " " $ Left(Args, i);
	TypeDT0 = float(ArgOf(Args, "dt0", "0"));
	TypeCps = float(ArgOf(Args, "cps", "9"));
	TypeHold = float(ArgOf(Args, "hold", "0.6"));
	TypeDrop = float(ArgOf(Args, "drop", "0.7"));
	TypeState = 1;
	DDLog("TYPE", "armed|dt0=" $ TypeDT0 $ "|text=" $ TypeText);
}

function string ArgOf(string S, string Key, string Def)
{
	local int i;
	i = InStr(S, " " $ Key $ "=");
	if (i < 0)
		return Def;
	S = Mid(S, i + Len(Key) + 2);
	i = InStr(S, " ");
	if (i >= 0)
		S = Left(S, i);
	return S;
}

// Console's own short message lines (drawn when the HUD does not draw messages).
simulated function DrawSingleView(Canvas C)
{
	if (HudMode != 0)
		return;
	Super.DrawSingleView(C);
}

event NotifyLevelChange()
{
	Super.NotifyLevelChange();
	Watcher = None;
	DDLog("LEVELCHANGE", "");
}

exec function DDStatus()
{
	EnsureWatcher();
	if (Watcher != None)
		Watcher.ReportState("STATUS");
	else
		DDLog("STATUS", "nodemo=1");
}

exec function DDPlayers()
{
	EnsureWatcher();
	if (Watcher != None)
		Watcher.ReportPlayers();
}

// Show (1) or hide (0) the HUD. Hiding also hides center/kill messages and the
// short message lines (cleared every tick by the watcher) for clean cinematic shots.
exec function DDHud(bool bShow)
{
	if (bShow)
		DDHudMode(0);
	else
		DDHudMode(2);
}

// 0 = original HUD, 1 = cinematic (crosshair + kill messages), 2 = blank,
// 3 = clean with crosshair (crosshair + name tags, no messages at all).
exec function DDHudMode(int M)
{
	HudMode = Clamp(M, 0, 3);
	bCleanHud = HudMode == 2;
	ClearMessages();
	EnsureWatcher();
	if (Watcher != None)
		Watcher.UpdateHud();
	DDLog("HUD", "mode=" $ HudMode);
}

// Automation: close windows that the demo opens by itself (checked every tick by the watcher).
exec function DDAutoClose(bool bOn)
{
	bAutoClose = bOn;
	DDLog("AUTOCLOSE", "on=" $ bOn);
}

// While a UWindow is open (e.g. a server "rules" page replayed from a demo), the stock console sends every key to
// the window and never runs key bindings. The automation delivers its commands with Scroll Lock
// ("exec ...\runtime\cmd.txt"), so run that binding here as well; all other keys behave as before.
// (Complements ddautoclose: commands still arrive in the ticks before the watcher closes the window, and for
// windows that ddautoclose is off for.)
state UWindow
{
	event bool KeyEvent(EInputKey Key, EInputAction Action, FLOAT Delta)
	{
		local string B;
		if (Key == IK_ScrollLock && Action == IST_Press && Viewport != None && Viewport.Actor != None)
		{
			B = Viewport.Actor.ConsoleCommand("KEYBINDING ScrollLock");
			DDLog("EXEC", "uwindow=1|bind=" $ B);
			if (B != "")
				Viewport.Actor.ConsoleCommand(B);
			return true;
		}
		return Super.KeyEvent(Key, Action, Delta);
	}
}

// Name tags (free-cam shots): "ddtag 3 7" or "ddtag" to clear.
exec function DDTag(string Ids)
{
	if (Ids == "")
		TagIds = "";
	else
		TagIds = " " $ Ids $ " ";
	DDLog("TAG", "ids=" $ Ids);
}

// Scripted camera, see DDCam.uc: "ddcam mode=orbit tgt=3 r=300 h=80 w=25"; "ddcam mode=off".
exec function DDCam(string Args)
{
	EnsureWatcher();
	if (Watcher == None)
		return;
	if (Watcher.Cam == None)
	{
		Watcher.Cam = Watcher.Spawn(class'DDCam');
		Watcher.Cam.Con = self;
	}
	if (Watcher.Take != None && Watcher.Take.bActive)
		Watcher.Take.Go(false);
	Watcher.Cam.Configure(Args);
}

// Keys for "ddcam mode=path kdt=0.1": "ddpath clear", "ddpath add p=x,y,z at=x,y,z fov=90" (see DDCam.uc and
// tools\mapgen\cam_path.py, which writes the whole key list as one command file).
exec function DDPath(string Args)
{
	EnsureWatcher();
	if (Watcher == None)
		return;
	if (Watcher.Cam == None)
	{
		Watcher.Cam = Watcher.Spawn(class'DDCam');
		Watcher.Cam.Con = self;
	}
	if (Args ~= "clear")
		Watcher.Cam.PathN = 0;
	else if (Left(Args, 4) ~= "add ")
		Watcher.Cam.PathAdd(Mid(Args, 4));
	else if (Left(Args, 6) ~= "render")
	{
		Watcher.Cam.StartRender(Mid(Args, 6));
		return;
	}
	DDLog("PATH", "keys=" $ Watcher.Cam.PathN);
}

// One-take camera timeline, see DDTake.uc: "ddtake clear", "ddtake add start=545 blend=1.5 mode=follow tgt=4 ...",
// "ddtake go", "ddtake off".
exec function DDTake(string Args)
{
	EnsureWatcher();
	if (Watcher == None)
		return;
	if (Watcher.Take == None)
	{
		Watcher.Take = Watcher.Spawn(class'DDTake');
		Watcher.Take.Con = self;
	}
	if (Args ~= "clear")
		Watcher.Take.Clear();
	else if (Args ~= "go")
	{
		if (Watcher.Cam != None)
			Watcher.Cam.bActive = false;   // the single ddcam must not fight the take
		Watcher.Take.Go(true);
	}
	else if (Args ~= "off" || Args == "")
		Watcher.Take.Go(false);
	else if (Left(Args, 4) ~= "add ")
		Watcher.Take.Add(Mid(Args, 4));
}

// Bullet-time sniper bullet, see DDBullet.uc: "ddbullet from=x,y,z to=x,y,z tk=<demo s> dur=5 gore=1"; "ddbullet off".
exec function DDBullet(string Args)
{
	EnsureWatcher();
	if (Watcher == None)
		return;
	if (Watcher.Bullet == None)
	{
		Watcher.Bullet = Watcher.Spawn(class'DDBullet');
		if (Watcher.Bullet == None)
		{
			DDLog("BULLET", "failed=spawn");
			return;
		}
		Watcher.Bullet.Con = self;
	}
	Watcher.Bullet.Configure(Args);
}

// Map tests: "ddtrace from=x,y,z to=x,y,z" runs the same kind of trace an instant-hit weapon uses (actors included)
// and logs what it hits: DD|TRACE|hit=<actor>|class=<class>|loc=x,y,z. Used to check whether beams cross portals.
exec function DDTrace(string Args)
{
	local vector A, B, HL, HN;
	local actor H;

	if (Viewport == None || Viewport.Actor == None)
		return;
	A = DDVec(ArgOf(" " $ Args, "from", "0,0,0"));
	B = DDVec(ArgOf(" " $ Args, "to", "0,0,0"));
	H = Viewport.Actor.Trace(HL, HN, B, A, true);
	DDLog("TRACE", "hit=" $ H $ "|loc=" $ int(HL.X) $ "," $ int(HL.Y) $ "," $ int(HL.Z));
}

function vector DDVec(string S)
{
	local vector V;
	local int i;

	i = InStr(S, ",");
	V.X = float(Left(S, i));
	S = Mid(S, i + 1);
	i = InStr(S, ",");
	V.Y = float(Left(S, i));
	V.Z = float(Mid(S, i + 1));
	return V;
}

// Kill probe: "ddprobe k=<killer id> v=<victim id>" logs both pawns every tick (PROBE) and new carcasses (CARC);
// "ddprobe off".
exec function DDProbe(string Args)
{
	EnsureWatcher();
	if (Watcher == None)
		return;
	if (Args == "" || Args ~= "off")
	{
		Watcher.bProbe = false;
		DDLog("PROBE", "on=False");
		return;
	}
	Watcher.ProbeK = int(ArgOf(" " $ Args, "k", "-1"));
	Watcher.ProbeV = int(ArgOf(" " $ Args, "v", "-1"));
	Watcher.bProbe = true;
	DDLog("PROBE", "on=True|k=" $ Watcher.ProbeK $ "|v=" $ Watcher.ProbeV);
}

// Speed ramp in demo time: "ddramp 58.0:1,58.3:0.02" (exponential between keyframes); "ddramp off" clears.
exec function DDRamp(string Args)
{
	EnsureWatcher();
	if (Watcher == None)
		return;
	if (Args == "" || Args ~= "off")
	{
		Watcher.RampN = 0;
		DDLog("RAMP", "n=0");
		return;
	}
	Watcher.SetRamp(Args);
}

// Rich scan logging: positions, shock balls, combos, shots, flag bases.
exec function DDRich(bool bOn)
{
	EnsureWatcher();
	if (Watcher != None)
		Watcher.bRich = bOn;
	DDLog("RICH", "on=" $ bOn);
}

// Hide gibs, carcasses and blood.
exec function DDNoGore(bool bOn)
{
	EnsureWatcher();
	if (Watcher != None)
		Watcher.bNoGore = bOn;
	DDLog("NOGORE", "on=" $ bOn);
}

// Remove all blood / scorch decals (they pile up over the whole seek); new ones keep appearing.
exec function DDDecals()
{
	local Decal D;
	local int N;
	if (Viewport == None || Viewport.Actor == None)
		return;
	foreach Viewport.Actor.AllActors(class'Decal', D)
	{
		D.Destroy();
		N++;
	}
	DDLog("DECALS", "cleared=" $ N);
}

// Log every actor class once (discovery of mod classes).
exec function DDCensus(bool bOn)
{
	EnsureWatcher();
	if (Watcher != None)
		Watcher.bCensus = bOn;
}

// ZeroPing beam fix (DDWatcher.BeamFix), on by default; "ddbeamfix 0" shows the demo's raw double beam again.
exec function DDBeamFix(bool bOn)
{
	EnsureWatcher();
	if (Watcher != None)
		Watcher.bBeamFix = bOn;
	DDLog("BEAMFIX", "on=" $ bOn);
}

// Log every Effects actor once (FX) and every shock beam when its data changes (BEAM); BEAMFIX lines show the fix.
exec function DDBeams(bool bOn)
{
	EnsureWatcher();
	if (Watcher != None)
		Watcher.bBeamLog = bOn;
	DDLog("BEAMS", "on=" $ bOn);
}

// Free-form marker, used by the automation to correlate log and video.
exec function DDMark(string S)
{
	DDLog("MARK", S);
}
