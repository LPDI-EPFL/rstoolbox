# @Author: Jaume Bonet <bonet>
# @Date:   09-Mar-2018
# @Email:  jaume.bonet@gmail.com
# @Filename: mutants.py
# @Last modified by:   bonet
# @Last modified time: 27-Mar-2018


import itertools
import re

import pandas as pd
import numpy as np

from .getters import _check_type, _get_available, _check_column


def get_identified_mutants( self ):
    """
    List for which sequence identifiers mutants have been calculated

    :return: :class:`list`

    :raises:
        :TypeError: If the data container is not :class:`~pandas.DataFrame`
            or :class:`~pandas.Series`
    """
    _check_type(self)
    return _get_available(self, "mutants_")


def get_mutations( self, seqID ):
    """
    Return the mutantions data for `seqID` available in the container.

    :param seqID: Identifier of the sequence of interest.
    :type seqID: :py:class:`str`

    :return: :py:class:`str` or :py:class:`~pandas.Series`

    :raises:
        :TypeError: If the data container is not `~pandas.DataFrame`
            or :py:class:`~pandas.Series`
        :KeyError: If the column `mutants_[seqID]` is cannot be found.
    """
    _check_type(self)
    return self[_check_column(self, "mutants", seqID)]


def get_mutation_positions( self, seqID ):
    """
    Return the mutantion positions data for `seqID` available in the container.

    :param seqID: Identifier of the sequence of interest.
    :type seqID: :py:class:`str`

    :return: :py:class:`str` or :py:class:`~pandas.Series`

    :raises:
        :TypeError: If the data container is not `~pandas.DataFrame`
            or :py:class:`~pandas.Series`
        :KeyError: If the column `mutant_positions_[seqID]` is cannot be found.
    """
    _check_type(self)
    return self[_check_column(self, "mutant_positions", seqID)]


def get_mutation_count( self, seqID ):
    """
    Return the number of mutantion positions data for `seqID` available in the container.

    :param seqID: Identifier of the sequence of interest.
    :type seqID: :class:`str`

    :return: :class:`str` or :class:`~pandas.Series`

    :raises:
        :TypeError: If the data container is not `~pandas.DataFrame`
            or :class:`~pandas.Series`
        :KeyError: If the column `mutant_count_[seqID]` is cannot be found.
    """
    _check_type(self)
    return self[_check_column(self, "mutant_count", seqID)]


def identify_mutants( self, seqID ):
    """
    Checks the sequence in column sequence_<seqID> againts the reference_sequence.
    Adds to the container two new columns: mutants_<seqID>, which lists
    the mutations of the particular decoy vs. the reference_sequence, mutant_positions_<seqID>
    just with those same positions and mutant_count_<seqID> with the count of the number of
    mutations. Reference and design sequence must be of the same length.

    :param seqID: Identifier of the sequence of interest.
    :type seqID: py:class:`str`

    :return: Changes the container and returns it
    """
    def mutations( reference, sequence, shift=1 ):
        data = []
        datn = []
        assert len(reference) == len(sequence)
        for i in range(len(reference)):
            if reference[i].upper() != sequence[i].upper():
                data.append(reference[i].upper() + str(i + shift) + sequence[i].upper())
                datn.append(str(i + shift))
        return ",".join(data), ",".join(datn), len(data)

    shift   = self.get_reference_shift(seqID)
    refseq  = self.get_reference_sequence(seqID)
    mutants = "mutants_{0}".format(seqID)
    mposits = "mutant_positions_{0}".format(seqID)
    mcounts = "mutant_count_{0}".format(seqID)
    if isinstance(self, pd.DataFrame):
        self[[mutants, mposits, mcounts]] = self.apply(
            lambda row: mutations(refseq, row.get_sequence(seqID), shift),
            axis=1, result_type="expand" )
    elif isinstance(self, pd.Series):
        a, b, c = mutations(refseq, self.get_sequence(seqID), shift)
        self[mutants], self[mposits], self[mcounts] = a, b, c

    return self


def generate_mutant_variants( self, seqID, mutations, keep_scores=False ):
    """
    Expands the selected sequences by ensuring that all the provided mutant combinations.
    Thus, something such as::

        df.generate_mutant_variants("A", [(20, "AIV"), (31, "EDQR")])

    Will generate all the variant sequences of "A" that combine the expected mutations in
    position 20 and 31 (according to the reference shift). That would be a total of 3*4
    combinations plus the original sequences.

    Alters the names of the designs in **description**.

    :param seqID: Identifier of the sequence sets of interest.
    :type seqID: :py:class:`str`
    :param mutations: List of mutations to generate in a format (position, variants)
    :type mutations: :py:class:`list`[(:py:class:`int`, :py:class:`str`),..]
    :param keep_scores: Attach to each variant the scores comming from the source sequence.
        This is not really recommended, as it can get confusing.
    :type keep_scores: :py:class:`bool`

    :return: :py:class:`.DesignFrame`
    """
    def multiplex( row, seqID, muts ):
        seqNM = _check_column(row, "sequence", seqID)
        idNM = "description"
        shift = row.get_reference_shift(seqID)
        seq   = list(row[seqNM])
        for p in muts:
            seq[p[0] - shift] = p[1]
        data = {seqNM: ["".join(x) for x in itertools.product(*seq)]}
        data[seqNM].insert(0, row[seqNM])
        name = row.get_id()
        if not bool(re.search("_v\d+$", row.get_id())):
            data[idNM] = [name + "_v{0:04d}".format(x) for x in range(len(data[seqNM]))]
            data[idNM][0] = name
        else:
            data[idNM] = [name + "_v{0:04d}".format(x) for x in range(1, len(data[seqNM]) + 1)]
        if keep_scores:
            for col in row.index:
                if col not in [seqNM, idNM]:
                    data[col] = [row[col]] * len(data[idNM])
        else:
            for seq in row.get_available_sequences():
                if seq != seqID:
                    data[_check_column(row, "sequence", seq)] = row.get_sequence(seq)
        df = row._constructor_expanddim(data)
        return df

    if isinstance(self, pd.DataFrame):
        designs = []
        for i, row in self.iterrows():
            designs.append(multiplex(row, seqID, mutations))
        df = pd.concat(designs)
    elif isinstance(self, pd.Series):
        df = multiplex(self, seqID, mutations)
    else:
        raise NotImplementedError

    df.transfer_reference(self)

    avail_seqs = df.get_available_sequences()
    seqs = [_check_column(df, "sequence", seq) for seq in avail_seqs]
    df.drop_duplicates(seqs, inplace=True)
    for seq in avail_seqs:
        df = df.identify_mutants(seq)
    if len(avail_seqs) > 1:
        muts = ["mutant_count_{}".format(seq) for seq in avail_seqs]
        df["mutant_count_all"] = df[muts].sum(axis=1)

    return df.reset_index(drop=True)


def generate_mutants_from_matrix( self, seqID, matrix, count,
                                  key_residues=None, limit_refseq=False ):
    """
    From a provided positional frequency matrix, generates ``count`` random variants.

    It takes into account the individual frequency assigned to each residue type and
    position.

    For each :class:`.SeriesFrame`, it will generate a :class:`.DesignFrame` in which the
    original sequence becomes the ``reference_sequence``, inheriting the ``reference_shift``.

    .. warning::
        This is a **computationaly expensive** function. Take this in consideration when trying
        to run it.

    Each :class:`.DesignFrame` will have the following structure:

    ======================  ============================================
    Column                                                Data Content
    ======================  ============================================
    **description**         Identifier fo the mutant
    **sequence_<seqID>**    Sequence content
    **pssm_score_<seqID>**  Score obtained by applying ``matrix``
    ======================  ============================================

    :param seqID: Identifier of the sequence sets of interest.
    :type seqID: :class:`str`
    :param matrix: Positional frequency matrix (*column:* residue type).
    :type matrix: :class:`~pandas.DataFrame`
    :param count: Expected number of **unique** generated combinations. If the number is
        bigger than the possible options, it will default to the total amount of options.
    :type count: :class:`int`
    :param key_residues: Residues over which to apply the matrix.
    :type key_residues: Union[:class:`.Selection`, :func:`list`, :class:`int`, :class:`str`]
    :param limit_refseq: When :data:`True`, pick only residue types with probabilities
        equal or higher to the source sequence.
    :type limit_refseq: :class:`bool`

    :return: :func:`list` of :class:`.DesignFrame` - New set of design sequences.

    .. seealso::
        :meth:`.DesignFrame.score_by_pssm`
        :meth:`.SeriesFrame.score_by_pssm`
    """
    # TODO: evaluate count < possible combinations
    # BODY: (matrix > 0).sum(axis=1).prod()
    # TODO: make sure of shift for both matrix and sequence
    # BODY: so that it works in pair with the rest of the library
    from rstoolbox.components import get_selection
    from rstoolbox.components import DesignSeries, DesignFrame

    data = []
    if isinstance(self, pd.DataFrame):
        for index, row in self.iterrows():
            data.extend(row.generate_mutants_from_matrix(seqID, matrix, count,
                                                         key_residues, limit_refseq))
        return data

    if key_residues is not None:
        key_residues = get_selection(key_residues, seqID, 1, matrix.shape[0])
    else:
        key_residues = range(1, matrix.shape[0] + 1)

    seqnm = "sequence_{}".format(seqID)
    data.append(DesignFrame([], columns=["description", seqnm]))
    name  = self.get_id()

    while data[-1].shape[0] < count:
        seqaa = list(self.get_sequence(seqID))
        thisname = name + "_v{0:04d}".format(data[-1].shape[0] + 1)
        for aap in key_residues:
            matI = matrix.loc[aap].copy()
            if limit_refseq:
                matI[matI < matI[seqaa[aap - 1]]] = 0
                matI = matI / matI.sum()
            seqaa[aap - 1] = np.random.choice(matI.index.values, 1, p=list(matI))[0]
        if "".join(seqaa) == self.get_sequence(seqID):
            continue
        data[-1] = data[-1].append(DesignSeries([thisname, "".join(seqaa)],
                                                ["description", seqnm]),
                                   ignore_index=True)
        data[-1].drop_duplicates([seqnm])
    data[-1].add_reference(seqID, self.get_sequence(seqID), shift=self.get_reference_shift(seqID))
    data[-1] = data[-1].score_by_pssm(seqID, matrix)
    return data


def generate_wt_reversions( self, seqID=None ):
    """
    Expand the selected sequences by generating all the combinatorial options to revert to
    the reference (WT) sequence.

    Alters the names of the designs in **description** column.

    :param seqID: Identifier of the sequence sets of interest. If none is provided, WT reversion
        is applied to all available sequences.
    :type seqID: :class:`str`

    :return: :class:`.DesignFrame`
    """
    def format_mutations( mutations ):
        mutations = mutations.split(",")
        muts = []
        for m in mutations:
            m = m.strip()
            muts.append((int(re.search("(\d+)", m).group(1)),
                        "".join([m[0], m[-1]])))
        return muts

    if seqID is None:
        seqID = self.get_available_sequences()
        adf = self.copy()
        for seq in seqID:
            adf = adf.generate_wt_reversions(seq)
    else:
        adf = []
        if "mutants_{}".format(seqID) not in self:
            self.identify_mutants(seqID)

        if isinstance(self, pd.DataFrame):
            designs = []
            for i, row in self.iterrows():
                mutations = format_mutations(row["mutants_{}".format(seqID)])
                designs.append(row.generate_mutant_variants(seqID, mutations))
            df = pd.concat(designs)
        elif isinstance(self, pd.Series):
            mutations = format_mutations(self["mutants_{}".format(seqID)])
            df = self.generate_mutant_variants(seqID, mutations)
        else:
            raise NotImplementedError
        adf.append(df)
        adf = pd.concat(adf)

    avail_seqs = adf.get_available_sequences()
    seqs = [_check_column(adf, "sequence", seq) for seq in avail_seqs]
    adf.drop_duplicates(seqs, inplace=True)
    return adf.reset_index(drop=True)


def score_by_pssm( self, seqID, pssm ):
    """
    Score sequences according to a provided PSSM matrix.

    Generates new column by applying the PSSM score to each position
    of the requested sequences:

    ======================  =====================================
    New Column                                       Data Content
    ======================  =====================================
    **pssm_score_<seqID>**  Score obtained by applying ``pssm``
    ======================  =====================================

    :param seqID: Identifier of the sequence sets of interest.
    :type seqID: :class:`str`
    :param pssm: PSSM matrix data.
    :type pssm: :class:`~pandas.DataFrame`

    :return: Union[:class:`.DesignSerie`, :class:`.DesignFrame`]
        - Itself with the new column.

    :raises:
        :NotImplementedError: if ``self`` is not :class:`~pandas.Series`
            or :class:`~pandas.DataFrame`.
        :AssertionError: if the length of the ``pssm`` does not match that
            of the sequence.
    """
    def evaluate_sequence(seq, pssm):
        score = 0
        assert len(seq) == pssm.shape[0]
        for i, aa in enumerate(seq):
            if aa in list(pssm.columns):
                score += pssm.iloc[i][aa]
        return score

    outcol = "pssm_score_{}".format(seqID)
    if isinstance(self, pd.Series):
        self[outcol] = evaluate_sequence(self.get_sequence(seqID), pssm)
    elif isinstance(self, pd.DataFrame):
        self[outcol] = self.apply(lambda row: evaluate_sequence(row.get_sequence(seqID), pssm),
                                  axis=1)
    else:
        raise NotImplementedError

    return self