"""Windows standalone Shield Rod installer. Frozen with Python/Tk included."""

from pathlib import Path

import argparse

import contextlib

import json

import queue

import sys

import threading

import traceback

import tkinter as tk

from tkinter import ttk, filedialog, messagebox

import installer_core as core



def resources():

    return Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'resources'



class LogWriter:

    def __init__(self, events):

        self.events = events

    def write(self, text):

        if text.strip():

            self.events.put(('log', text.rstrip()))

        return len(text)

    def flush(self):

        pass



def gui():

    window = tk.Tk()

    window.title('Shield Rod DLC Installer')

    window.geometry('820x740')

    window.minsize(690, 680)

    frame = ttk.Frame(window, padding=18)

    frame.pack(fill='both', expand=True)

    ttk.Label(frame, text='Shield Rod DLC', font=('Segoe UI', 19, 'bold')).pack(anchor='w')

    ttk.Label(frame, text='Alucard’s Shield Rod and its thirteen shield spells • Alucard’s five familiar cards (Bat, Ghost, Faerie, Demon, Sword)\n'
              'Shanoa’s Refectio glyph • Original SotN graphics and sounds from your own disc', wraplength=760).pack(anchor='w', pady=(4, 8))

    ttk.Label(frame, text='Required: official DLC Chapters 7, 8 and 11 installed and the game launched once with them • '
              'the .setup folder (setup files) from your HarmonyRecomp compile still in the recomp folder • your USA SotN disc. '
              'Optional: a USA Order of Ecclesia ROM for Refectio’s original effect art (generated art otherwise).',
              wraplength=760).pack(anchor='w', pady=(0, 8))

    game, disc, content, ooe = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()

    controls = []

    def row(label, variable, browse):

        ttk.Label(frame, text=label).pack(anchor='w', pady=(5, 2))

        line = ttk.Frame(frame)

        line.pack(fill='x')

        entry = ttk.Entry(line, textvariable=variable)

        entry.pack(side='left', fill='x', expand=True)

        button = ttk.Button(line, text='Browse…', command=browse)

        button.pack(side='left', padx=(8, 0))

        controls.extend([entry, button])

    def folder(variable):

        chosen = filedialog.askdirectory(parent=window)

        if chosen:

            variable.set(chosen)

    def choose_disc():

        chosen = filedialog.askopenfilename(parent=window, title='Choose USA Symphony of the Night disc',

                    filetypes=[('SotN disc image', '*.cue *.bin *.iso'), ('All files', '*.*')])

        if chosen:

            disc.set(chosen)

    row('HarmonyRecomp folder (contains harmonyrecomp.exe)', game, lambda: folder(game))

    row('Your USA SotN disc (SLUS-00067; ISO, CUE, or data-track BIN)', disc, choose_disc)

    def choose_ooe():

        chosen = filedialog.askopenfilename(parent=window, title='Choose USA Order of Ecclesia ROM (optional)',

                    filetypes=[('Nintendo DS ROM', '*.nds'), ('All files', '*.*')])

        if chosen:

            ooe.set(chosen)

    row('Your USA Order of Ecclesia ROM (optional; .nds, for Refectio’s original effect art)', ooe, choose_ooe)

    row('DLC location (optional; leave blank to detect. Accepts the dlc folder or the extracted Chapter 8 folder)', content, lambda: folder(content))

    ttk.Label(frame, text='Close the game first. Installation may take a few minutes.\nUninstall restores the original files; the SotN disc and ROM are not needed to uninstall.', wraplength=760).pack(anchor='w', pady=(12, 10))

    events = queue.Queue()

    busy = [False]

    logbox = tk.Text(frame, height=9, wrap='word', state='disabled', font=('Consolas', 9))

    logbox.pack(fill='both', expand=True)

    bar = ttk.Progressbar(frame, mode='indeterminate')

    bar.pack(fill='x', pady=(8, 10))

    actions = ttk.Frame(frame)

    actions.pack(fill='x')

    def run(action):

        if busy[0]:

            return

        if not game.get().strip():

            messagebox.showerror('Select a recomp', 'Choose the HarmonyRecomp folder first.', parent=window)

            return

        busy[0] = True

        for control in controls:

            control.configure(state='disabled')

        bar.start()

        selected_game, selected_disc, selected_content = game.get(), disc.get(), content.get() or None

        selected_ooe = ooe.get().strip() or None

        def worker():

            try:

                with contextlib.redirect_stdout(LogWriter(events)), contextlib.redirect_stderr(LogWriter(events)):

                    if action == 'install':

                        core.install(selected_game, selected_disc, resources(),

                                     lambda text: events.put(('log', text)), selected_content, selected_ooe)

                    else:

                        core.restore(selected_game, lambda text: events.put(('log', text)))

                events.put(('done', 'Shield Rod, the familiar cards and Refectio installed. Start HarmonyRecomp normally.' if action == 'install' else 'Shield Rod, the familiar cards and Refectio removed. Original files restored.'))

            except Exception as error:

                if getattr(error, 'details', None):

                    events.put(('log', str(error) + '\n' + error.details))

                else:

                    events.put(('log', traceback.format_exc()))

                events.put(('error', str(error)))

        threading.Thread(target=worker, daemon=True).start()

    install_button = ttk.Button(actions, text='Install Shield Rod', command=lambda: run('install'))

    install_button.pack(side='left')

    uninstall_button = ttk.Button(actions, text='Uninstall / Restore', command=lambda: run('uninstall'))

    uninstall_button.pack(side='left', padx=10)

    controls.extend([install_button, uninstall_button])

    def save_source():

        chosen = filedialog.asksaveasfilename(parent=window, initialfile='ShieldRod_SOURCE_AND_LICENSES.zip', defaultextension='.zip', filetypes=[('ZIP archive', '*.zip')])

        if chosen:

            import shutil

            shutil.copy2(resources() / 'SOURCE_AND_LICENSES.zip', chosen)

    ttk.Button(actions, text='Source / licenses...', command=save_source).pack(side='left')

    def copy_log():

        window.clipboard_clear()

        window.clipboard_append(logbox.get('1.0', 'end-1c'))

    ttk.Button(actions, text='Copy log', command=copy_log).pack(side='left', padx=10)

    ttk.Button(actions, text='Close', command=lambda: close()).pack(side='right')

    def close():

        if busy[0]:

            messagebox.showinfo('Operation in progress', 'Wait for the operation to finish. A recovery journal is saved before any installed file changes.', parent=window)

        else:

            window.destroy()

    window.protocol('WM_DELETE_WINDOW', close)

    def poll():

        try:

            while True:

                kind, text = events.get_nowait()

                if kind == 'log':

                    logbox.configure(state='normal')

                    logbox.insert('end', text + '\n')

                    logbox.see('end')

                    logbox.configure(state='disabled')

                else:

                    busy[0] = False

                    bar.stop()

                    for control in controls:

                        control.configure(state='normal')

                    (messagebox.showinfo if kind == 'done' else messagebox.showerror)('Shield Rod Installer', text, parent=window)

        except queue.Empty:

            pass

        window.after(100, poll)

    poll()

    window.mainloop()



def main():

    parser = argparse.ArgumentParser()

    parser.add_argument('--install', action='store_true')

    parser.add_argument('--uninstall', action='store_true')

    parser.add_argument('--check', action='store_true')

    parser.add_argument('--game')

    parser.add_argument('--disc')

    parser.add_argument('--content')

    parser.add_argument('--ooe')

    parser.add_argument('--report')

    args = parser.parse_args()

    if not any([args.install, args.uninstall, args.check]):

        gui()

        return

    logs = []

    try:

        if args.uninstall:

            result = core.restore(args.game, logs.append)

        elif args.check:

            if (core.paths(args.game)[0] / core.STATE_DIR / 'installation.json').is_file():

                # Install uninstalls the recorded installation first; check that part only.

                report = {'ok': True, 'result': {'compatible': True, 'replaces_installation': True}, 'log': logs}

                core.write_json(Path(args.report), report) if args.report else print(json.dumps(report, indent=2))

                return

            result = core.preflight(args.game, resources(), args.content, logs.append)

            # Also exercise the frozen disc reader/dependencies without writes.

            import sotn_disc

            import hashlib

            disc = sotn_disc.Disc(args.disc)

            from zipfile import ZipFile

            with ZipFile(resources() / 'traces.zip') as z:

                assert len(z.namelist()) == 184

            assert hashlib.sha1(disc.get('DRA.BIN')).hexdigest() == '2eac5f7162e77416166c2511c787995488f01c37'

            disc.f.close()

            if args.ooe:

                core.extras.refectio_art(args.ooe, logs.append)

            result = {'compatible': True, 'content': str(result[2]), 'chapter8': str(result[4]), 'chapter7': str(result[6]), 'chapter11': str(result[7])}

        else:

            result = core.install(args.game, args.disc, resources(), logs.append, args.content, args.ooe)

        report = {'ok': True, 'result': result, 'log': logs}

    except Exception as error:

        report = {'ok': False, 'error': str(error), 'details': getattr(error, 'details', None),
                  'traceback': traceback.format_exc(), 'log': logs}

    if args.report:

        core.write_json(Path(args.report), report)

    elif sys.stdout:

        print(json.dumps(report, indent=2))

    if not report['ok']:

        raise SystemExit(1)



if __name__ == '__main__':

    main()

