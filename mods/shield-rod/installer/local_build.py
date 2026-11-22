"""Build against an individual 0.6.0 installation without modifying its cache.

Read CMake/Ninja metadata as data. Invoke only the existing compiler, never
execute Ninja rules, setup scripts, shell command strings or CMake hooks.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
import executable_patch

HOOKS = set('82450658 824519C8 824526D0 823C4EC8 824823A0 823C4C40 823C5098 82246DF0 825CEFA0 825CED10 82451AA8 8245D9A0 824476B8 824827F0 8244BF10 8244CA98'.split()
            # Familiar cards and Refectio: player update, skill factory, equipment icon column.
            + '8244FFF8 82487EF8 823E0410 823E6958 823EA810 823ED418 823F46A8 823F47C8'.split())
MOD_SOURCES = ('shield_rod.cpp', 'shield_rod_bridge.cpp', 'alucard_familiar.cpp', 'refectio.cpp', 'equip_card_icon.cpp')
MOD_OBJECTS = {'nathan_dss_damage.cpp.obj'} | {name + '.obj' for name in MOD_SOURCES}

# Temporary fixes to HarmonyRecomp's own source files. Each replaces the
# player's cached object only when their file is the unmodified v0.6.0 one
# (SHA-256 of its text with LF line ends), so a recomp that already ships a fix
# keeps its own. Delete an entry once the recomp fixes it upstream.
RECOMP_FIXES = {
    # DLC package files named longer than 42 characters were deleted and
    # unpacked again on every launch, wiping the chest edits in them
    # (modding/docs/BUG_DLC_LONG_FILENAMES.md, patches/dlc-long-names.patch).
    'dlc.cpp': '0817cb18e5241452873ac0f68582dedd6393752eb2749991934f606af12b016b',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_digest(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def recomp_fixes(src):
    """The RECOMP_FIXES that apply to this setup's source (unmodified v0.6.0 files only)."""
    return [name for name, stock in RECOMP_FIXES.items()
            if (src / 'src' / name).is_file() and text_digest(src / 'src' / name) == stock]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def windows_arguments(text):
    count = ctypes.c_int()
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    values = shell.CommandLineToArgvW('dummy ' + text, ctypes.byref(count))
    if not values:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [values[i] for i in range(1, count.value)]
    finally:
        kernel = ctypes.WinDLL('kernel32')
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(values)


def ninja_words(text):
    # Ninja escapes a space/colon/dollar using '$', not shell quoting.
    words, word, i = [], '', 0
    while i < len(text):
        ch = text[i]
        if ch == '$':
            i += 1
            require(i < len(text) and text[i] in ' :$', 'Unsupported Ninja variable in a build path.')
            word += text[i]
        elif ch.isspace():
            if word:
                words.append(word); word = ''
        else:
            word += ch
        i += 1
    if word:
        words.append(word)
    return words


def read_edges(path):
    text = path.read_text(encoding='utf-8').replace('$\r\n', '').replace('$\n', '')
    edges, current = {}, None
    for line in text.splitlines():
        if line.startswith('build '):
            # Target paths are relative here; escaped drive colons are skipped.
            split = re.search(r'(?<!\$): ', line)
            require(split is not None, 'Unrecognized Ninja build edge.')
            if not line[split.end():].startswith(('CXX_COMPILER_', 'CXX_EXECUTABLE_LINKER_')):
                current = None
                continue
            targets = ninja_words(line[6:split.start()])
            inputs = ninja_words(line[split.end():])
            current = dict(inputs=inputs[1:], rule=inputs[0], variables={})
            for target in targets:
                edges[target.replace('\\', '/')] = current
        elif line.startswith('  ') and current is not None and ' = ' in line:
            key, value = line.strip().split(' = ', 1)
            current['variables'][key] = value
        elif line and not line.startswith((' ', '#')):
            current = None
    return edges


def locate(game):
    game = Path(game).resolve()
    candidates = [game / '.setup']
    log = game / 'setup.log'
    if log.is_file():
        # An install may have been moved away from its original setup directory.
        for sdk in re.findall(r'--sdk-dir\s+"([^"]+)"', log.read_text(errors='replace')):
            p = Path(sdk)
            if p.name.lower() == 'sdk' and p.parent.name.lower() == 'package':
                candidates.append(p.parent.parent)
    for setup in candidates:
        src = setup / 'package/src'
        build = src / 'out/build/win-amd64-release'
        if (build / 'build.ninja').is_file() and (setup / 'toolchain/llvm/bin/clang++.exe').is_file():
            return setup.resolve()
    raise ValueError('This is a locally compiled HarmonyRecomp build. Keep or restore the .setup folder from Wrexxial 0.6.0 Setup, then retry. It must contain the source, cached build objects, SDK and compiler. No separate executable patch is needed. If .setup was deleted, rerun official 0.6.0 Setup first.')


def plan(game, setup=None, verify_executable=True):
    setup = Path(setup).resolve() if setup else locate(game)
    src = setup / 'package/src'
    build = src / 'out/build/win-amd64-release'
    release = setup / 'package/release.txt'
    require(release.is_file() and release.read_text().strip() == 'v0.6.0', 'The retained setup must be Wrexxial HarmonyRecomp v0.6.0.')
    cache = (build / 'CMakeCache.txt').read_text(errors='replace')
    require('HARMONYRECOMP_VERSION:STRING=v0.6.0' in cache, 'The retained build cache is not HarmonyRecomp 0.6.0.')
    if verify_executable:
        require((build / 'harmonyrecomp.exe').is_file(), 'The retained setup is missing its original build output. Rerun official Setup first.')
        require(executable_patch.canonical_pe((build / 'harmonyrecomp.exe').read_bytes()) ==
                executable_patch.canonical_pe((Path(game) / 'harmonyrecomp.exe').read_bytes()),
                'The installed executable does not match this setup cache. Rerun Wrexxial 0.6.0 Setup for this recomp folder, then retry.')
    sdk = setup / 'package/sdk'
    require(digest(sdk / 'bin/rexruntime.dll') == digest(Path(game) / 'rexruntime.dll'), 'The retained SDK does not match the installed runtime.')
    edges = read_edges(build / 'build.ninja')
    require('harmonyrecomp.exe' in edges, 'No executable link target in the retained build cache.')
    link = edges['harmonyrecomp.exe']
    fixes = recomp_fixes(src)
    fixed_objects = {name + '.obj' for name in fixes}
    objects, replaced = [], {}
    for name in link['inputs']:
        if name in ('|', '||'):
            break
        p = (build / name).resolve()
        require(p.is_relative_to(build.resolve()) and p.is_file() and p.suffix == '.obj', f'Missing cached object: {p}. Rerun official Setup first.')
        if p.name in fixed_objects:
            replaced[p.name] = p  # stock object, linked again if the mod is not built
        elif p.name not in MOD_OBJECTS:
            require('nathan' not in str(p).lower(), 'Unexpected Nathan object in the retained build.')
            objects.append((name.replace('\\', '/'), p))
    require(set(replaced) == fixed_objects, 'The retained build cache is missing a recomp source object.')
    require(objects, 'No cached game objects found.')
    template = next((edges[name] for name, p in objects if p.name == 'main.cpp.obj'), None)
    require(template is not None, 'No main compilation settings in the retained cache.')
    require('REX_FUNC_TABLE_BASE=0x8C000000ull' in template['variables'].get('DEFINES', ''), 'Unsupported main function-table layout.')
    return dict(setup=setup, src=src, build=build, sdk=sdk, edges=edges, link=link,
                objects=objects, template=template, compiler=setup / 'toolchain/llvm/bin/clang++.exe',
                fixes=fixes, fixed_objects=replaced)


def environment(setup):
    env = os.environ.copy()
    # Official Setup can use portable MSVC instead of a system installation.
    for path in [setup / 'msvc/env.json', setup / 'msvc/environment.json', setup / 'msvc-env.json']:
        if path.is_file():
            data = json.loads(path.read_text())
            for key in ('INCLUDE', 'LIB'):
                if data.get(key):
                    env[key] = data[key]
    roots = list(setup.glob('**/VC/Tools/MSVC'))
    if roots:
        msvc = sorted(roots[0].glob('*'))[-1]
        portable = roots[0].parents[2]
        kits = portable / 'Windows Kits/10'
        versions = sorted((kits / 'Include').glob('10.*'))
        if versions:
            version = versions[-1].name
            includes = [msvc / 'include'] + [kits / 'Include' / version / p for p in ('ucrt', 'shared', 'um', 'winrt', 'cppwinrt')]
            libraries = [msvc / 'lib/x64'] + [kits / 'Lib' / version / p / 'x64' for p in ('ucrt', 'um')]
            env['INCLUDE'] = ';'.join(str(p) for p in includes if p.is_dir())
            env['LIB'] = ';'.join(str(p) for p in libraries if p.is_dir())
    return env


def run(arguments, cwd, env, log):
    result = subprocess.run([str(v) for v in arguments], cwd=cwd, env=env, capture_output=True,
                            text=True, errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        log(result.stdout[-12000:] + result.stderr[-12000:])
        raise RuntimeError('Shield Rod runtime build failed. The original game and setup files have not been changed. Compiler details are in the log.')


def build(context, work, resources, log=print, shield=True):
    """All compiler outputs go in work; the source/setup cache stays read-only."""
    root = Path(work) / 'runtime-build'
    root.mkdir(parents=True, exist_ok=True)
    source = root / 'src'
    generated = root / 'generated/default'
    source.mkdir(exist_ok=True); generated.mkdir(parents=True, exist_ok=True)
    env = environment(context['setup'])
    jobs, replacements, seen = [], {}, set()
    if shield:
        with zipfile.ZipFile(resources / 'SOURCE_AND_LICENSES.zip') as archive:
            for name in archive.namelist():
                if name.startswith('runtime/') and name.endswith(('.cpp', '.h')):
                    target = source / Path(name).name
                    target.write_bytes(archive.read(name))
        shutil.copy2(context['src'] / 'generated/default/harmonyrecomp_init.h', generated / 'harmonyrecomp_init.h')
        call = re.compile(r'\bsub_(' + '|'.join(sorted(HOOKS)) + r')\(ctx, base\);')
        for name, obj in context['objects']:
            edge = context['edges'].get(name)
            if not edge or 'harmonyrecomp_recomp.' not in obj.name:
                continue
            native_source = Path(edge['inputs'][0])
            if not native_source.is_absolute():
                native_source = context['build'] / native_source
            code = native_source.read_text(encoding='utf-8')
            defined = set(re.findall(r'DEFINE_REX_FUNC\(sub_([0-9A-F]+)\)', code)) & HOOKS
            seen |= defined
            if not defined:
                continue
            # Only same-shard weak aliases require indirect dispatch. Calls
            # from other translation units bind to the new strong overrides.
            code = call.sub(lambda m: 'REX_CALL_INDIRECT_FUNC(0x' + m[1] + ');', code)
            staged = generated / native_source.name
            staged.write_text(code, encoding='utf-8')
            output = root / obj.name
            jobs.append((staged, output, edge))
            replacements[name] = output
        require(seen == HOOKS, 'Retained generated code is missing required TU2 hooks: ' + ', '.join(sorted(HOOKS - seen)))
        for name in MOD_SOURCES + tuple(context.get('fixes', ())):
            jobs.append((source / name, root / (name + '.obj'), context['template']))
    def compile_one(job):
        staged, output, edge = job
        variables = edge['variables']
        args = [context['compiler']]
        for key in ('DEFINES', 'INCLUDES', 'FLAGS'):
            args += windows_arguments(variables.get(key, ''))
        args += ['-I' + str(generated), '-o', output, '-c', staged]
        run(args, root, env, log)
        return output.name
    if jobs:
        log(f'Building Shield Rod for this 0.6.0 installation ({len(jobs)} source files; the first build may take several minutes)...')
        with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as executor:
            futures = [executor.submit(compile_one, job) for job in jobs]
            for index, future in enumerate(as_completed(futures), 1):
                log(f'Compiled {index}/{len(jobs)}: {future.result()}')
    objects = [replacements.get(name, obj) for name, obj in context['objects']]
    if shield:
        objects += [root / (name + '.obj') for name in MOD_SOURCES + tuple(context.get('fixes', ()))]
    else:
        objects += list(context.get('fixed_objects', {}).values())
    variables = context['link']['variables']
    libraries = windows_arguments(variables['LINK_LIBRARIES'])
    rsp = root / 'runtime.rsp'
    rsp.write_text(subprocess.list2cmdline([p.as_posix() for p in objects] + [v.replace(chr(92), "/") for v in libraries]), encoding='utf-8')
    output = root / 'harmonyrecomp.exe'
    map_file = root / 'harmonyrecomp.map'
    flags = windows_arguments(variables.get('LINK_FLAGS', ''))
    flags = [('/MAP:' + str(map_file)) if f.upper().startswith('/MAP:') else f for f in flags]
    if not any(f.upper().startswith('/MAP:') for f in flags):
        flags += ['-Xlinker', '/MAP:' + str(map_file)]
    args = [context['compiler'], '-nostartfiles', '-nostdlib'] + windows_arguments(variables.get('FLAGS', '')) + flags
    args += ['@' + str(rsp), '-o', output, '-Xlinker', '/MANIFEST:EMBED', '-Xlinker', '/version:0.0']
    log('Linking the runtime with this installation’s original game and DLC modules...')
    run(args, root, env, log)
    mapping = map_file.read_text(errors='replace')
    require('nathan_dss_damage.cpp.obj' not in mapping, 'Nathan code entered the runtime build.')
    if shield:
        linked = output.read_bytes()
        require('shield_rod_bridge.cpp.obj' in mapping and b'[shield rod]' in linked, 'Shield Rod integration missing from the linked runtime.')
        require('alucard_familiar.cpp.obj' in mapping and b'[familiar]' in linked and b'[refectio]' in linked,
                'Familiar card or Refectio integration missing from the linked runtime.')
        if 'dlc.cpp' in context.get('fixes', ()):
            require(b'is longer than 42 characters' in linked, 'The DLC file name fix is missing from the linked runtime.')
        else:
            log('Note: this setup\'s dlc.cpp is not the unmodified 0.6.0 file; keeping its own DLC handling.')
    return output, map_file
