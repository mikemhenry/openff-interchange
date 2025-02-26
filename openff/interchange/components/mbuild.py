"""Utilities for processing and interfacing with mBuild models."""
from typing import TYPE_CHECKING

from openff.toolkit.topology import Molecule, Topology
from openff.utilities.utilities import has_package, requires_package
from openmm import unit

if has_package("mbuild") or TYPE_CHECKING:
    import mbuild as mb


@requires_package("mbuild")
def offmol_to_compound(off_mol: "Molecule") -> "mb.Compound":
    """
    Convert an OpenFF Molecule into an mBuild Compound.

    Examples
    --------
    .. code-block:: pycon

        >>> from openff.toolkit.topology import Molecule
        >>> from openff.interchange.components.mbuild import offmol_to_compound
        >>> mol = Molecule.from_smiles("CCO")
        >>> compound = offmol_to_compound(mol)
        >>> type(compound), compound.n_particles, compound.n_bonds
        (<class 'mbuild.compound.Compound'>, 9, 8)

    """
    if not off_mol.has_unique_atom_names:
        off_mol.generate_unique_atom_names()

    if off_mol.n_conformers == 0:
        off_mol.generate_conformers(n_conformers=1)

    comp = mb.Compound()
    comp.name = off_mol.name

    for a in off_mol.atoms:
        atom_comp = mb.Particle(name=a.element.symbol)
        comp.add(atom_comp, label=a.name)

    for b in off_mol.bonds:
        comp.add_bond((comp[b.atom1_index], comp[b.atom2_index]))

    comp.xyz = off_mol.conformers[0].value_in_unit(unit.nanometer)

    return comp


@requires_package("mbuild")
def offtop_to_compound(off_top: "Topology") -> "mb.Compound":
    """
    Convert an OpenFF Topology into an mBuild Compound.

    Examples
    --------
    .. code-block:: pycon

        >>> from openff.toolkit.topology import Molecule, Topology
        >>> from openff.interchange.components.mbuild import offtop_to_compound
        >>> ethanol = Molecule.from_smiles("CCO")
        >>> ethanol.name = "ETH"
        >>> methane = Molecule.from_smiles("C")
        >>> methane.name = "MET"
        >>> top = Topology.from_molecules([ethanol, ethanol, methane, methane])
        >>> compound = offtop_to_compound(top)
        >>> type(compound), len(compound.children), compound.n_particles, compound.n_bonds
        (<class 'mbuild.compound.Compound'>, 4, 28, 24)

    """
    sub_comps = []

    for top_mol in off_top.topology_molecules:
        # TODO: This could have unintended consequences if the TopologyMolecule
        # has atoms in a different order than the reference Molecule
        this_comp = offmol_to_compound(top_mol.reference_molecule)
        sub_comps.append(this_comp)

    comp = mb.Compound(subcompounds=sub_comps)
    return comp
