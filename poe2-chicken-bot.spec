block_cipher = None

a = Analysis(['main.py'],
             pathex=['.'],
             hiddenimports=[],
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
          name='poe2-chicken-bot', upx=True, console=False, onefile=True, icon='media/poe2-chicken-bot.ico')

coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, upx=True, name='poe2-chicken-bot')