# -*- mode: python ; coding: utf-8 -*-

# pyinstaller spec file to build a stand-alone Windows .exe application

block_cipher = None


a = Analysis(['MasterFlatMaker.py'],
             pathex=['\\\\Mac\\Dropbox\\Dropbox\\EWHO\\Application Development\\MasterFlatMaker'],
             binaries=[],
             datas=[('MainWindow.ui', '.'),
             ('ConsoleWindow.ui', '.'),
             ('PreferencesWindow.ui','.')],
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
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='MasterFlatMaker',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False )
