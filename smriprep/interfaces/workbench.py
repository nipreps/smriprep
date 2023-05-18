from nipype.interfaces.base import CommandLineInputSpec, File, TraitedSpec, traits
from nipype.interfaces.workbench.base import WBCommand


class CreateSignedDistanceVolumeInputSpec(CommandLineInputSpec):
    surf_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=0,
        desc="Input surface GIFTI file (.surf.gii)",
    )
    ref_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=1,
        desc="NIfTI volume in the desired output space (dims, spacing, origin)",
    )
    out_file = File(
        name_source=["surf_file"],
        name_template="%s_distvol.nii.gz",
        argstr="%s",
        position=2,
        desc="Name of output volume containing signed distances",
    )
    out_mask = File(
        name_source=["surf_file"],
        name_template="%s_distmask.nii.gz",
        argstr="-roi-out %s",
        desc="Name of file to store a mask where the ``out_file`` has a computed value",
    )
    fill_value = traits.Float(
        0.0,
        mandatory=False,
        usedefault=True,
        argstr="-fill-value %f",
        desc="value to put in all voxels that don't get assigned a distance",
    )
    exact_limit = traits.Float(
        5.0,
        usedefault=True,
        argstr="-exact-limit %f",
        desc="distance for exact output in mm",
    )
    approx_limit = traits.Float(
        20.0,
        usedefault=True,
        argstr="-approx-limit %f",
        desc="distance for approximate output in mm",
    )
    approx_neighborhood = traits.Int(
        2,
        usedefault=True,
        argstr="-approx-neighborhood %d",
        desc="size of neighborhood cube measured from center to face in voxels, default 2 = 5x5x5",
    )
    winding_method = traits.Enum(
        "EVEN_ODD",
        "NEGATIVE",
        "NONZERO",
        "NORMALS",
        argstr="-winding %s",
        usedefault=True,
        desc="winding method for point inside surface test",
    )


class CreateSignedDistanceVolumeOutputSpec(TraitedSpec):
    out_file = File(desc="Name of output volume containing signed distances")
    out_mask = File(
        desc="Name of file to store a mask where the ``out_file`` has a computed value"
    )


class CreateSignedDistanceVolume(WBCommand):
    """Create signed distance volume from surface

    Computes the signed distance function of the surface.  Exact distance is
    calculated by finding the closest point on any surface triangle to the
    center of the voxel.  Approximate distance is calculated starting with
    these distances, using dijkstra's method with a neighborhood of voxels.
    Specifying too small of an exact distance may produce unexpected results.

    The NORMALS winding method uses the normals of triangles and edges, or the
    closest triangle hit by a ray from the point.  This method may be
    slightly faster, but is only reliable for a closed surface that does not
    cross through itself.  All other methods count entry (positive) and exit
    (negative) crossings of a vertical ray from the point, then counts as
    inside if the total is odd, negative, or nonzero, respectively.

    Command help string::

        CREATE SIGNED DISTANCE VOLUME FROM SURFACE

        wb_command -create-signed-distance-volume
           <surface> - the input surface
           <refspace> - a volume in the desired output space (dims, spacing, origin)
           <outvol> - output - the output volume

           [-roi-out] - output an roi volume of where the output has a computed
              value
              <roi-vol> - output - the output roi volume

           [-fill-value] - specify a value to put in all voxels that don't get
              assigned a distance
              <value> - value to fill with (default 0)

           [-exact-limit] - specify distance for exact output
              <dist> - distance in mm (default 5)

           [-approx-limit] - specify distance for approximate output
              <dist> - distance in mm (default 20)

           [-approx-neighborhood] - voxel neighborhood for approximate calculation
              <num> - size of neighborhood cube measured from center to face, in
                 voxels (default 2 = 5x5x5)

           [-winding] - winding method for point inside surface test
              <method> - name of the method (default EVEN_ODD)

           Computes the signed distance function of the surface.  Exact distance is
           calculated by finding the closest point on any surface triangle to the
           center of the voxel.  Approximate distance is calculated starting with
           these distances, using dijkstra's method with a neighborhood of voxels.
           Specifying too small of an exact distance may produce unexpected results.
           Valid specifiers for winding methods are as follows:

           EVEN_ODD (default)
           NEGATIVE
           NONZERO
           NORMALS

           The NORMALS method uses the normals of triangles and edges, or the
           closest triangle hit by a ray from the point.  This method may be
           slightly faster, but is only reliable for a closed surface that does not
           cross through itself.  All other methods count entry (positive) and exit
           (negative) crossings of a vertical ray from the point, then counts as
           inside if the total is odd, negative, or nonzero, respectively.
    """

    input_spec = CreateSignedDistanceVolumeInputSpec
    output_spec = CreateSignedDistanceVolumeOutputSpec
    _cmd = "wb_command -create-signed-distance-volume"


class SurfaceSphereProjectUnprojectInputSpec(TraitedSpec):
    """COPY REGISTRATION DEFORMATIONS TO DIFFERENT SPHERE.

    wb_command -surface-sphere-project-unproject
       <sphere-in> - a sphere with the desired output mesh
       <sphere-project-to> - a sphere that aligns with sphere-in
       <sphere-unproject-from> - <sphere-project-to> deformed to the desired
          output space
       <sphere-out> - output - the output sphere

       Background: A surface registration starts with an input sphere, and moves
       its vertices around on the sphere until it matches the template data.
       This means that the registration deformation is actually represented as
       the difference between two separate files - the starting sphere, and the
       registered sphere.  Since the starting sphere of the registration may not
       have vertex correspondence to any other sphere (often, it is a native
       sphere), it can be inconvenient to manipulate or compare these
       deformations across subjects, etc.

       The purpose of this command is to be able to apply these deformations
       onto a new sphere of the user's choice, to make it easier to compare or
       manipulate them.  Common uses are to concatenate two successive separate
       registrations (e.g. Human to Chimpanzee, and then Chimpanzee to Macaque)
       or inversion (for dedrifting or symmetric registration schemes).

       <sphere-in> must already be considered to be in alignment with one of the
       two ends of the registration (if your registration is Human to
       Chimpanzee, <sphere-in> must be in register with either Human or
       Chimpanzee).  The 'project-to' sphere must be the side of the
       registration that is aligned with <sphere-in> (if your registration is
       Human to Chimpanzee, and <sphere-in> is aligned with Human, then
       'project-to' should be the original Human sphere).  The 'unproject-from'
       sphere must be the remaining sphere of the registration (original vs
       deformed/registered).  The output is as if you had run the same
       registration with <sphere-in> as the starting sphere, in the direction of
       deforming the 'project-to' sphere to create the 'unproject-from' sphere.

       Note that this command cannot check for you what spheres are aligned with
       other spheres, and using the wrong spheres or in the incorrect order will
       not necessarily cause an error message.  In some cases, it may be useful
       to use a new, arbitrary sphere as the input, which can be created with
       the -surface-create-sphere command.

       Example 1: You have a Human to Chimpanzee registration, and a Chimpanzee
       to Macaque registration, and want to combine them.  If you use the Human
       sphere registered to Chimpanzee as sphere-in, the Chimpanzee standard
       sphere as project-to, and the Chimpanzee sphere registered to Macaque as
       unproject-from, the output will be the Human sphere in register with the
       Macaque.

       Example 2: You have a Human to Chimpanzee registration, but what you
       really want is the inverse, that is, the sphere as if you had run the
       registration from Chimpanzee to Human.  If you use the Chimpanzee
       standard sphere as sphere-in, the Human sphere registered to Chimpanzee
       as project-to, and the standard Human sphere as unproject-from, the
       output will be the Chimpanzee sphere in register with the Human.

       Technical details: Each vertex of <sphere-in> is projected to a triangle
       of <sphere-project-to>, and its new position is determined by the
       position of the corresponding triangle in <sphere-unproject-from>.  The
       output is a sphere with the topology of <sphere-in>, but coordinates
       shifted by the deformation from <sphere-project-to> to
       <sphere-unproject-from>.  <sphere-project-to> and <sphere-unproject-from>
       must have the same topology as each other, but <sphere-in> may have any
       topology."""

    sphere_in = File(
        desc="a sphere with the desired output mesh",
        exists=True,
        argstr="%s",
        position=0,
    )
    sphere_project_to = File(
        desc="a sphere that aligns with sphere-in",
        exists=True,
        argstr="%s",
        position=1,
    )
    sphere_unproject_from = File(
        desc="<sphere-project-to> deformed to the desired output space",
        exists=True,
        argstr="%s",
        position=2,
    )
    sphere_out = traits.File(
        name_template="%s_unprojected.surf.gii",
        name_source=["sphere_in"],
        desc="the output sphere",
        argstr="%s",
        position=3,
    )

class SurfaceSphereProjectUnprojectOutputSpec(TraitedSpec):
    sphere_out = File(desc="the output sphere", exists=True)


class SurfaceSphereProjectUnproject(WBCommand):
    """COPY REGISTRATION DEFORMATIONS TO DIFFERENT SPHERE.

    Example
    -------
    >>> from smriprep.interfaces.workbench import SurfaceSphereProjectUnproject
    >>> sphere_project = SurfaceSphereProjectUnproject()
    >>> sphere_project.inputs.sphere_in = 'sub-01_hemi-L_sphere.surf.gii'
    >>> sphere_project.inputs.sphere_project_to = 'tpl-fsLR_hemi-L_den-32k_sphere.surf.gii'
    >>> sphere_project.inputs.sphere_unproject_from = 'lh.sphere.reg.surf.gii'
    >>> sphere_project.cmdline
    'wb_command -surface-sphere-project-unproject sub-01_hemi-L_sphere.surf.gii \
    tpl-fsLR_hemi-L_den-32k_sphere.surf.gii lh.sphere.reg.surf.gii \
    sub-01_hemi-L_sphere.surf_unprojected.surf.gii'
    """
    input_spec = SurfaceSphereProjectUnprojectInputSpec
    output_spec = SurfaceSphereProjectUnprojectOutputSpec
    _cmd = "wb_command -surface-sphere-project-unproject"


class SurfaceResampleInputSpec(TraitedSpec):
    """RESAMPLE A SURFACE TO A DIFFERENT MESH

    wb_command -surface-resample
      <surface-in> - the surface file to resample
      <current-sphere> - a sphere surface with the mesh that the input surface
         is currently on
      <new-sphere> - a sphere surface that is in register with <current-sphere>
         and has the desired output mesh
      <method> - the method name
      <surface-out> - output - the output surface file

      [-area-surfs] - specify surfaces to do vertex area correction based on
         <current-area> - a relevant surface with <current-sphere> mesh
         <new-area> - a relevant surface with <new-sphere> mesh

      [-area-metrics] - specify vertex area metrics to do area correction based
         on
         <current-area> - a metric file with vertex areas for <current-sphere>
            mesh
         <new-area> - a metric file with vertex areas for <new-sphere> mesh

      Resamples a surface file, given two spherical surfaces that are in
      register.  If ADAP_BARY_AREA is used, exactly one of -area-surfs or
      -area-metrics must be specified.  This method is not generally
      recommended for surface resampling, but is provided for completeness.

      The BARYCENTRIC method is generally recommended for anatomical surfaces,
      in order to minimize smoothing.

      For cut surfaces (including flatmaps), use -surface-cut-resample.

      Instead of resampling a spherical surface, the
      -surface-sphere-project-unproject command is recommended.

      The <method> argument must be one of the following:

      ADAP_BARY_AREA
      BARYCENTRIC
    """

    surface_in = File(
        desc="the surface file to resample",
        exists=True,
        mandatory=True,
        argstr="%s",
        position=0,
    )
    current_sphere = File(
        desc="a sphere surface with the mesh that the input surface is currently on",
        exists=True,
        mandatory=True,
        argstr="%s",
        position=1,
    )
    new_sphere = File(
        desc="a sphere surface that is in register with <current-sphere> and has the desired output mesh",
        exists=True,
        mandatory=True,
        argstr="%s",
        position=2,
    )
    method = traits.Enum(
        "ADAP_BARY_AREA",
        "BARYCENTRIC",
        desc="the method name",
        mandatory=True,
        argstr="%s",
        position=3,
    )
    surface_out = traits.File(
        name_template="%s_resampled.surf.gii",
        name_source=["surface_in"],
        keep_extension=False,
        desc="the output surface file",
        argstr="%s",
        position=4,
    )
    correction_source = traits.Enum(
        "area_surfs",
        "area_metrics",
        desc="specify surfaces or vertex area metrics to do vertex area correction based on",
        argstr="-%s",
        position=5,
    )
    current_area = File(
        desc="a relevant surface with <current-sphere> mesh",
        exists=True,
        argstr="%s",
        position=6,
        requires=['correction_source'],
    )
    new_area = File(
        desc="a relevant surface with <new-sphere> mesh",
        exists=True,
        argstr="%s",
        position=7,
        requires=['correction_source'],
    )


class SurfaceResampleOutputSpec(TraitedSpec):
    surface_out = File(desc="the output surface file", exists=True)


class SurfaceResample(WBCommand):
    """RESAMPLE A SURFACE TO A DIFFERENT MESH.

    Example
    -------
    >>> from smriprep.interfaces.workbench import SurfaceResample
    >>> surface_resample = SurfaceResample()
    >>> surface_resample.inputs.surface_in = 'sub-01_hemi-L_midthickness.surf.gii'
    >>> surface_resample.inputs.current_sphere = 'sub-01_hemi-L_sphere.surf.gii'
    >>> surface_resample.inputs.new_sphere = 'tpl-fsLR_hemi-L_den-32k_sphere.surf.gii'
    >>> surface_resample.inputs.method = 'BARYCENTRIC'
    >>> surface_resample.cmdline
    'wb_command -surface-resample sub-01_hemi-L_midthickness.surf.gii \
    sub-01_hemi-L_sphere.surf.gii tpl-fsLR_hemi-L_den-32k_sphere.surf.gii \
    BARYCENTRIC sub-01_hemi-L_midthickness.surf_resampled.surf.gii'
    """

    input_spec = SurfaceResampleInputSpec
    output_spec = SurfaceResampleOutputSpec
    _cmd = "wb_command -surface-resample"
