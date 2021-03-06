# -*- mode: python ; coding: utf-8 -*-

# This spec file is used with pyinstaller to generate a stand-alone mac application


block_cipher = None


a = Analysis(['MasterFlatMaker.py'],
             pathex=['/Users/richard/DropBox/dropbox/EWHO/Application Development/MasterFlatMaker'],
             binaries=[],
             datas=[('MainWindow.ui', '.'),
             ('ConsoleWindow.ui', '.'),
             ('PreferencesWindow.ui', '.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='MasterFlatMaker',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='MasterFlatMaker')
app = BUNDLE(coll,
             name='MasterFlatMaker.app',
             icon=None,
             bundle_identifier=None)
