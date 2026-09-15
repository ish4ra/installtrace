# Standalone EXE එක දැන් තිබෙනවා

[InstallTrace.exe download කරන්න](https://github.com/ish4ra/installtrace/releases/download/v0.1.0/InstallTrace.exe).
EXE එක සඳහා Python install කරන්න අවශ්‍ය නැහැ. Windows CI tests 17ක් සහ executable
GUI/capture smoke test pass වී ඇත. පරීක්ෂා කළ runner එක Windows Server 2025 යි;
ඔබේ Windows 10/11 PC එකේ මුලින් Load demo ඔබා බලන්න. මෙය unsigned preview එකකි.

පහත උපදෙස් source code එකෙන් run කිරීමටයි.

# InstallTrace — පටන් ගන්න

මෙය Windows සඳහා ලියූ මුල් prototype එකකි. Source code එක run කරන්න Python 3.10+
අවශ්‍යයි. මේ package එකේ කලින් build කළ EXE එකක් නැහැ.

1. ZIP එක extract කරන්න.
2. Python installer එකේ Python Launcher සහ Tcl/Tk තෝරා install කරන්න.
3. `Start-InstallTrace.cmd` double-click කරන්න.
4. මුලින් **Load demo** ඔබන්න. මෙහි තියෙන්නේ sample data; ඔබේ PC එක scan කළ දත්ත නොවේ.
5. සැබෑ test එකකට folder paths සකස් කරන්න. App එකේ AppData folder එකත් අවශ්‍ය නම් add කරන්න.
6. **Before install → Capture** ඔබා JSON file එක save කරන්න. Scan එක ඉවර වෙනකම් ඉන්න.
7. ඔබ පරීක්ෂා කරන software එක වෙනම install කරන්න.
8. **After install → Capture** කර **Compare installation** ඔබන්න.
9. Row එකක් click කළාම පෙර/පසු අගයන් බලන්න පුළුවන්.
10. Software එක uninstall කළාට පස්සේ **After uninstall → Capture → Find leftovers** භාවිත කරන්න.

Snapshots save කරන්නේ scan කරන folders වලට පිටත තැනක තබන්න. හැම capture එකටම එකම
folders, hash limit, Windows user account සහ administrator level එක භාවිත කරන්න.

- **Added**: අලුතින් දකින්න ලැබුණු entry එකක්.
- **Modified**: වෙනස් වූ entry එකක්.
- **Removed**: පෙර තිබුණු නමුත් පසුව නොපෙනෙන entry එකක්.
- **Uncertain**: scan permissions/coverage ප්‍රශ්නයක් නිසා තහවුරු කරන්න බැරි වෙනසක්.
- **Review persistence**: startup/service/task වගේ entry එකක්. මෙය virus කියන තීන්දුවක් නොවේ.

Files, selected registry locations, services සහ scheduled tasks inspect කරනවා.
සියලු registry locations හෝ live processes/network traffic monitor කරන්නේ නැහැ.
Default එකෙන් 16 MiB දක්වා files hash කරනවා; විශාල files වල metadata පමණක් බලනවා.

මේ app එකෙන් installer එක run කරන්නේ හෝ leftovers delete කරන්නේ නැහැ.
වෙනස්කමක් තිබුණා කියලා ඒක installer එකෙන්ම වුණා කියලා ඔප්පු වෙන්නේ නැහැ.
Unknown installers පරීක්ෂා කරන්න disposable VM එකක් භාවිත කරන්න.

**Export report** මඟින් offline HTML report එකක් ගන්න පුළුවන්. Report වල personal paths,
registry values සහ command arguments තිබිය හැකි නිසා share කිරීමට කලින් බලන්න.

Windows build සහ පරීක්ෂණ තොරතුරු `VALIDATION.md` එකේ තියෙනවා.

වැඩි විස්තර, commands සහ GitHub upload steps `README.md` එකේ තියෙනවා.
