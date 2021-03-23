import numpy as np
import pytest
from openff.toolkit.topology import Molecule, Topology
from simtk import unit as omm_unit

from openff.system.stubs import ForceField
from openff.system.tests.energy_tests.lammps import (
    _write_lammps_input,
    get_lammps_energies,
)
from openff.system.tests.energy_tests.openmm import get_openmm_energies


@pytest.mark.parametrize("n_mols", [1, 2])
@pytest.mark.parametrize(
    "mol",
    [
        "C",
        "CC",  # Adds a proper torsion term(s)
        "OC=O",  # Simplest molecule with a multi-term torsion
        "CCOC",  # This hits t86, which has a non-1.0 idivf
        "C1COC(=O)O1",  # This adds an improper, i2
    ],
)
def test_to_lammps_single_mols(mol, n_mols):
    """
    Test that ForceField.create_openmm_system and System.to_openmm produce
    objects with similar energies

    TODO: Tighten tolerances
    TODO: Test periodic and non-periodic
    """

    parsley = ForceField("openff_unconstrained-1.0.0.offxml")

    mol = Molecule.from_smiles(mol)
    mol.generate_conformers(n_conformers=1)
    top = Topology.from_molecules(n_mols * [mol])
    mol.conformers[0] -= np.min(mol.conformers) * omm_unit.angstrom

    top.box_vectors = np.eye(3) * np.asarray([10, 10, 10]) * omm_unit.nanometer

    if n_mols == 1:
        positions = mol.conformers[0]
    elif n_mols == 2:
        positions = np.vstack(
            [mol.conformers[0], mol.conformers[0] + 3 * omm_unit.nanometer]
        )
        positions = positions * omm_unit.angstrom

    openff_sys = parsley.create_openff_system(topology=top)
    openff_sys.positions = positions.value_in_unit(omm_unit.nanometer)
    openff_sys.box = top.box_vectors

    reference = get_openmm_energies(
        off_sys=openff_sys, round_positions=3, electrostatics=False
    )

    lmp_energies = get_lammps_energies(
        off_sys=openff_sys, round_positions=3, electrostatics=False
    )

    _write_lammps_input(
        off_sys=openff_sys,
        file_name="tmp.in",
        electrostatics=False,
    )

    lmp_energies.compare(
        reference,
        custom_tolerances={
            "Nonbonded": 999 * omm_unit.kilojoule_per_mole,
            "Torsion": 0.005 * omm_unit.kilojoule_per_mole,
        },
    )
