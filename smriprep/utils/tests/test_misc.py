import pytest

from ..misc import fs_isRunning


def _gen_fsdir(tmp_path, isrunning):
    fsdir = tmp_path / 'sample_freesurfer'
    (fsdir / 'sub-01' / 'scripts').mkdir(parents=True)
    (fsdir / 'sub-01' / 'scripts' / 'recon-all.log').write_text('log')
    if isrunning:
        (fsdir / 'sub-01' / 'scripts' / 'IsRunning.rh').write_text('running')
        (fsdir / 'sub-01' / 'scripts' / 'IsRunning.lh').write_text('running')
    return fsdir


@pytest.mark.parametrize('isrunning,mtime_tol,error', [
    (False, 86400, None),
    (True, 86400, RuntimeError),
    (True, 0, None),
])
def test_fs_isRunning(tmp_path, isrunning, mtime_tol, error):
    fs_dir = _gen_fsdir(tmp_path, isrunning)
    if error is None:
        fs_isRunning(fs_dir, 'sub-01', mtime_tol=mtime_tol)
        assert not tuple(fs_dir.glob('**/IsRunning*'))
    else:
        with pytest.raises(error):
            fs_isRunning(fs_dir, 'sub-01', mtime_tol=mtime_tol)
        assert tuple(fs_dir.glob('**/IsRunning*'))
