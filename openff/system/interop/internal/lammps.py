from pathlib import Path
from typing import IO, TYPE_CHECKING, Dict, Union

import numpy as np
from simtk import unit as omm_unit

from openff.system import unit
from openff.system.exceptions import UnsupportedExportError
from openff.system.models import TopologyKey

if TYPE_CHECKING:
    from openff.system.components.system import System


def to_lammps(openff_sys: "System", file_path: Union[Path, str]):

    if isinstance(file_path, str):
        path = Path(file_path)
    if isinstance(file_path, Path):
        path = file_path

    n_atoms = openff_sys.topology.n_topology_atoms  # type: ignore[union-attr]
    if "Bonds" in openff_sys.handlers:
        n_bonds = len(openff_sys["Bonds"].slot_map.keys())
    else:
        n_bonds = 0
    if "Angles" in openff_sys.handlers:
        n_angles = len(openff_sys["Angles"].slot_map.keys())
    else:
        n_angles = 0
    if "ProperTorsions" in openff_sys.handlers:
        n_propers = len(openff_sys["ProperTorsions"].slot_map.keys())
    else:
        n_propers = 0
    if "ImproperTorsions" in openff_sys.handlers:
        n_impropers = len(openff_sys["ImproperTorsions"].slot_map.keys())
    else:
        n_impropers = 0

    with open(path, "w") as lmp_file:
        lmp_file.write("Title\n\n")

        lmp_file.write(f"{n_atoms} atoms\n")
        lmp_file.write(f"{n_bonds} bonds\n")
        lmp_file.write(f"{n_angles} angles\n")
        lmp_file.write(f"{n_propers} dihedrals\n")
        lmp_file.write(f"{n_impropers} impropers\n")

        lmp_file.write(f"\n{len(openff_sys['vdW'].potentials)} atom types")
        if n_bonds > 0:
            lmp_file.write(f"\n{len(openff_sys['Bonds'].potentials)} bond types")
        if n_angles > 0:
            lmp_file.write(f"\n{len(openff_sys['Angles'].potentials)} angle types\n")
        if n_propers > 0:
            lmp_file.write(
                f"\n{len(openff_sys['ProperTorsions'].potentials)} dihedral types\n"
            )
        if n_impropers > 0:
            lmp_file.write(
                f"\n{len(openff_sys['ImproperTorsions'].potentials)} improper types\n"
            )

        lmp_file.write("\n")

        # write types section

        x_min, y_min, z_min = np.min(
            openff_sys.positions.to(unit.angstrom), axis=0  # type: ignore[attr-defined]
        ).magnitude
        L_x, L_y, L_z = np.diag(openff_sys.box.to(unit.angstrom).magnitude)  # type: ignore[attr-defined]

        lmp_file.write(
            "{:.10g} {:.10g} xlo xhi\n"
            "{:.10g} {:.10g} ylo yhi\n"
            "{:.10g} {:.10g} zlo zhi\n".format(
                x_min,
                x_min + L_x,
                y_min,
                y_min + L_y,
                z_min,
                z_min + L_z,
            )
        )

        lmp_file.write("0.0 0.0 0.0 xy xz yz\n")

        lmp_file.write("\nMasses\n\n")

        vdw_handler = openff_sys["vdW"]
        atom_type_map = dict(enumerate(vdw_handler.potentials))
        slot_map_inv = dict({v: k for k, v in vdw_handler.slot_map.items()})

        for atom_type_idx, smirks in atom_type_map.items():
            # Find just one topology atom matching this SMIRKS by vdW
            matched_atom_idx = slot_map_inv[smirks].atom_indices[0]
            matched_atom = openff_sys.topology.atom(matched_atom_idx)  # type: ignore
            mass = matched_atom.atom.mass.value_in_unit(omm_unit.dalton)

            lmp_file.write("{:d}\t{:.8g}\n".format(atom_type_idx + 1, mass))

        lmp_file.write("\n\n")

        _write_pair_coeffs(
            lmp_file=lmp_file, openff_sys=openff_sys, atom_type_map=atom_type_map
        )

        if n_bonds > 0:
            _write_bond_coeffs(lmp_file=lmp_file, openff_sys=openff_sys)
        if n_angles > 0:
            _write_angle_coeffs(lmp_file=lmp_file, openff_sys=openff_sys)
        if n_propers > 0:
            _write_proper_coeffs(lmp_file=lmp_file, openff_sys=openff_sys)
        if n_impropers > 0:
            _write_improper_coeffs(lmp_file=lmp_file, openff_sys=openff_sys)

        _write_atoms(
            lmp_file=lmp_file, openff_sys=openff_sys, atom_type_map=atom_type_map
        )
        if n_bonds > 0:
            _write_bonds(lmp_file=lmp_file, openff_sys=openff_sys)
        if n_angles > 0:
            _write_angles(lmp_file=lmp_file, openff_sys=openff_sys)
        if n_propers > 0:
            _write_propers(lmp_file=lmp_file, openff_sys=openff_sys)
        if n_impropers > 0:
            _write_impropers(lmp_file=lmp_file, openff_sys=openff_sys)


def _write_pair_coeffs(lmp_file: IO, openff_sys: "System", atom_type_map: Dict):
    lmp_file.write("Pair Coeffs\n\n")

    vdw_handler = openff_sys["vdW"]

    for atom_type_idx, smirks in atom_type_map.items():
        params = vdw_handler.potentials[smirks].parameters

        sigma = params["sigma"].to(unit.angstrom).magnitude
        epsilon = params["epsilon"].to(unit.Unit("kilocalorie / mole")).magnitude

        lmp_file.write(
            "{:d}\t{:.8g}\t{:.8g}\n".format(atom_type_idx + 1, epsilon, sigma)
        )

    lmp_file.write("\n")


def _write_bond_coeffs(lmp_file: IO, openff_sys: "System"):
    lmp_file.write("Bond Coeffs\n\n")

    bond_handler = openff_sys.handlers["Bonds"]
    bond_type_map = dict(enumerate(bond_handler.potentials))

    for bond_type_idx, smirks in bond_type_map.items():
        params = bond_handler.potentials[smirks].parameters

        k = params["k"].to(unit.Unit("kilocalorie / mole / angstrom ** 2")).magnitude
        k = k * 0.5  # Account for LAMMPS wrapping 1/2 into k
        length = params["length"].to(unit.angstrom).magnitude

        lmp_file.write(f"{bond_type_idx+1:d} harmonic\t{k:.16g}\t{length:.16g}\n")

    lmp_file.write("\n")


def _write_angle_coeffs(lmp_file: IO, openff_sys: "System"):
    lmp_file.write("\nAngle Coeffs\n\n")

    angle_handler = openff_sys.handlers["Angles"]
    angle_type_map = dict(enumerate(angle_handler.potentials))

    for angle_type_idx, smirks in angle_type_map.items():
        params = angle_handler.potentials[smirks].parameters

        k = params["k"].to(unit.Unit("kilocalorie / mole / radian ** 2")).magnitude
        k = k * 0.5  # Account for LAMMPS wrapping 1/2 into k
        theta = params["angle"].to(unit.degree).magnitude

        lmp_file.write(f"{angle_type_idx+1:d} harmonic\t{k:.16g}\t{theta:.16g}\n")

    lmp_file.write("\n")


def _write_proper_coeffs(lmp_file: IO, openff_sys: "System"):
    lmp_file.write("\nDihedral Coeffs\n\n")

    proper_handler = openff_sys.handlers["ProperTorsions"]
    proper_type_map = dict(enumerate(proper_handler.potentials))

    for proper_type_idx, smirks in proper_type_map.items():
        params = proper_handler.potentials[smirks].parameters

        k = params["k"].to(unit.Unit("kilocalorie / mole")).magnitude
        n = int(params["periodicity"])
        phase = params["phase"].to(unit.degree).magnitude
        idivf = int(params["idivf"])
        k = k / idivf

        lmp_file.write(
            f"{proper_type_idx+1:d} fourier 1\t{k:.16g}\t{n:d}\t{phase:.16g}\n"
        )

    lmp_file.write("\n")


def _write_improper_coeffs(lmp_file: IO, openff_sys: "System"):
    lmp_file.write("\nImproper Coeffs\n\n")

    improper_handler = openff_sys.handlers["ImproperTorsions"]
    improper_type_map = dict(enumerate(improper_handler.potentials))

    for improper_type_idx, smirks in improper_type_map.items():
        params = improper_handler.potentials[smirks].parameters

        k = params["k"].to(unit.Unit("kilocalorie / mole")).magnitude
        n = int(params["periodicity"])
        phase = params["phase"].to(unit.degree).magnitude
        idivf = int(params["idivf"])
        k = k / idivf

        if (phase != 180) or (n != 2):
            raise UnsupportedExportError(
                "Improper exports to LAMMPS are funky and not well-supported "
                "at the moment, see PR #126"
            )

        # See https://lammps.sandia.gov/doc/improper_fourier.html
        # cos(n * x - pi) == - cos(n * x)
        # k * (1 + cos(n * phi - pi / 2)) == k * (1 - cos(n * phi))
        d = -1

        lmp_file.write(f"{improper_type_idx+1:d} cvff {k:.16g}\t{d:d}\t{n:.16g}\n")

    lmp_file.write("\n")


def _write_atoms(lmp_file: IO, openff_sys: "System", atom_type_map: Dict):
    lmp_file.write("\nAtoms\n\n")

    molecule_map = dict(enumerate(openff_sys.topology.topology_molecules))  # type: ignore[union-attr]
    molecule_map_inv = dict({v: k for k, v in molecule_map.items()})

    atom_type_map_inv = dict({v: k for k, v in atom_type_map.items()})

    electrostatics_handler = openff_sys.handlers["Electrostatics"]
    vdw_hander = openff_sys.handlers["vdW"]

    for atom_idx, atom in enumerate(openff_sys.topology.topology_atoms):  # type: ignore[union-attr]

        molecule_idx = molecule_map_inv[atom.topology_molecule]

        top_key = TopologyKey(atom_indices=(atom_idx,))
        pot_key = vdw_hander.slot_map[top_key]
        atom_type = atom_type_map_inv[pot_key]

        top_key = TopologyKey(atom_indices=(atom_idx,))
        charge = electrostatics_handler.charges[top_key].magnitude  # type: ignore[attr-defined]
        pos = openff_sys.positions[atom_idx].to(unit.angstrom).magnitude
        lmp_file.write(
            "{:d}\t{:d}\t{:d}\t{:.8g}\t{:.8g}\t{:.8g}\t{:.8g}\n".format(
                atom_idx + 1,
                molecule_idx + 1,
                atom_type + 1,
                charge,
                pos[0],
                pos[1],
                pos[2],
            )
        )


def _write_bonds(lmp_file: IO, openff_sys: "System"):
    lmp_file.write("\nBonds\n\n")

    bond_handler = openff_sys["Bonds"]
    bond_type_map = dict(enumerate(bond_handler.potentials))

    bond_type_map_inv = dict({v: k for k, v in bond_type_map.items()})

    for bond_idx, bond in enumerate(openff_sys.topology.topology_bonds):  # type: ignore[union-attr]
        # These are "topology indices"
        indices = tuple(sorted(a.topology_atom_index for a in bond.atoms))
        top_key = TopologyKey(atom_indices=indices)
        pot_key = bond_handler.slot_map[top_key]
        bond_type = bond_type_map_inv[pot_key]

        lmp_file.write(
            "{:d}\t{:d}\t{:d}\t{:d}\n".format(
                bond_idx + 1,
                bond_type + 1,
                indices[0] + 1,
                indices[1] + 1,
            )
        )


def _write_angles(lmp_file: IO, openff_sys: "System"):
    lmp_file.write("\nAngles\n\n")

    angle_handler = openff_sys["Angles"]
    angle_type_map = dict(enumerate(angle_handler.potentials))

    angle_type_map_inv = dict({v: k for k, v in angle_type_map.items()})

    for angle_idx, angle in enumerate(openff_sys.topology.angles):  # type: ignore[union-attr]
        # These are "topology indices"
        indices = tuple(a.topology_atom_index for a in angle)
        top_key = TopologyKey(atom_indices=indices)
        pot_key = angle_handler.slot_map[top_key]
        angle_type = angle_type_map_inv[pot_key]

        lmp_file.write(
            "{:d}\t{:d}\t{:d}\t{:d}\t{:d}\n".format(
                angle_idx + 1,
                angle_type + 1,
                indices[0] + 1,
                indices[1] + 1,
                indices[2] + 1,
            )
        )


def _write_propers(lmp_file: IO, openff_sys: "System"):
    lmp_file.write("\nDihedrals\n\n")

    proper_handler = openff_sys["ProperTorsions"]
    proper_type_map = dict(enumerate(proper_handler.potentials))

    proper_type_map_inv = dict({v: k for k, v in proper_type_map.items()})

    for proper_idx, proper in enumerate(openff_sys.topology.propers):  # type: ignore[union-attr]
        # These are "topology indices"
        indices = tuple(a.topology_atom_index for a in proper)
        for top_key, pot_key in proper_handler.slot_map.items():
            if indices == top_key.atom_indices:

                proper_type_idx = proper_type_map_inv[pot_key]

                lmp_file.write(
                    "{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\n".format(
                        proper_idx + 1,
                        proper_type_idx + 1,
                        indices[0] + 1,
                        indices[1] + 1,
                        indices[2] + 1,
                        indices[3] + 1,
                    )
                )


def _write_impropers(lmp_file: IO, openff_sys: "System"):
    lmp_file.write("\nImpropers\n\n")

    improper_handler = openff_sys["ImproperTorsions"]
    improper_type_map = dict(enumerate(improper_handler.potentials))

    improper_type_map_inv = dict({v: k for k, v in improper_type_map.items()})

    for improper_idx, improper in enumerate(openff_sys.topology.impropers):  # type: ignore[union-attr]
        # These are "topology indices"
        indices = tuple(a.topology_atom_index for a in improper)
        for top_key, pot_key in improper_handler.slot_map.items():
            if indices == top_key.atom_indices:

                improper_type_idx = improper_type_map_inv[pot_key]

                lmp_file.write(
                    "{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\n".format(
                        improper_idx + 1,
                        improper_type_idx + 1,
                        indices[0] + 1,
                        indices[1] + 1,
                        indices[2] + 1,
                        indices[3] + 1,
                    )
                )
