def is_skull_stripped(img, empty_sides=4, side_threshold=10):
    import numpy as np
    import nibabel as nb
    data = np.abs(nb.load(img).dataobj)
    sides = [data[0, :, :], data[:, 0, :], data[:, :, 0],
             data[-1, :, :], data[:, -1, :], data[:, :, -1]]
    return sum(np.sum(side) < side_threshold for side in sides) >= empty_sides
