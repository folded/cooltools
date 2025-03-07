import pandas as pd
import numpy as np
from functools import partial
from .. import expected

import click
from .util import validate_csv
from . import cli

@cli.command()
@click.argument(
    "expected_path",
    metavar="EXPECTED_PATH",
    type=str,
    callback=partial(validate_csv, default_column="balanced.sum"),
)
@click.argument(
    "output_prefix",
    metavar="OUTPUT_PREFIX",
    type=str,
    nargs=1
)
@click.option(
    "--bins-per-order-magnitude",
    metavar="bins_per_order_magnitude",
    help="How many bins per order of magnitude. "
         "Default of 10 has a ratio of neighboring bins of about 1.25",
    type=int,
    nargs=1,
    default=10,
    show_default=True
)
@click.option(
    "--bin-layout",
    metavar="bin_layout",
    help="'fixed' means that bins are exactly the same for different datasets, "
          "and only depend on bins_per_order_magnitude "
         "'longest_regio' means that the last bin will end at size of the longest region. "
         "\nGOOD: the last bin will have as much data as possible. "
         "\nBAD: bin edges will end up different for different datasets, "
         "you can't divide them by each other",
    type=click.Choice(["fixed", "longest_region"]),
    nargs=1,
    default='fixed',
    show_default=True
)
@click.option(
    "--min-nvalid",
    metavar="min_nvalid",
    help="For each region, throw out bins (log-spaced) that have less than min_nvalid "
         "valid pixels. This will ensure that each entree in Pc by region has at least "
         "n_valid valid pixels. "
         "Don't set it to zero, or it will introduce bugs. Setting it to 1 is OK, but "
         "not recommended.",
    type=int,
    nargs=1,
    default=200,
    show_default=True
)
@click.option(
    "--min-count",
    metavar="min_count",
    help="If counts are found in the data, then for each region, throw out bins "
         "(log-spaced) that have more than min_counts of counts.sum (raw Hi-C counts). "
         "This will ensure that each entree in P(s) by region has at least min_count "
         "raw Hi-C reads",
    type=int,
    nargs=1,
    default=50,
    show_default=True
)
@click.option(
    "--spread-funcs",
    metavar="spread_funcs",
    help="A way to estimate the spread of the P(s) curves between regions. "
    "* 'minmax' - the minimum/maximum of by-region P(s)\n"
    "* 'std' - weighted standard deviation of P(s) curves (may produce negative results)\n "
    "* 'logstd' (recommended) weighted standard deviation in logspace",
    type=click.Choice(["minmax", "std", "logstd"]),
    default='logstd',
    show_default=True,
    nargs=1,
)
@click.option(
    "--spread-funcs-slope",
    metavar="spread_funcs_slope",
    help="Same as spread-funcs, but for slope (derivative) ratehr than P(s)",
    type=click.Choice(["minmax", "std", "logstd"]),
    default='std',
    show_default=True,
    nargs=1,
)
@click.option(
    "--resolution",
    metavar="resolution",
    help="Data resolution in bp. If provided, additonal column of separation in bp "
    "(s_bp) will be added to the outputs",
    type=int,
    nargs=1,
)
def logbin_expected(
    expected_path,
    output_prefix,
    bins_per_order_magnitude,
    bin_layout,
    min_nvalid,
    min_count,
    spread_funcs,
    spread_funcs_slope,
    resolution
):
    """
    Logarithmically bin expected values generated using compute_expected for cis data.
    
    This smoothes the data, resulting in clearer plots and more robust analysis results.
    Also calculates derivative after gaussian smoothing.
    For a very detailed escription, see
    https://github.com/open2c/cooltools/blob/51b95c3bed8d00a5f1f91370fc5192d9a7face7c/cooltools/expected.py#L988

    EXPECTED_PATH : The paths to a .tsv file with output of compute_expected.
    Must include a header. Use the '::' syntax to specify a summary column name.
    
    OUTPUT_PREFIX: Output file name prefix to store the logbinned expected
    (prefix.log.tsv) and derivative (prefix.der.tsv) in the tsv format."
    """

    # unpack expected path and name as generated by click's callback to validate_csv:
    expected_path, exp_summary_name = expected_path
    # that's what we expect as column names:
    expected_columns = ["region", "diag", "n_valid", "count.sum", exp_summary_name]
    if exp_summary_name == "count.sum":
        expected_columns = ["region", "diag", "n_valid", exp_summary_name]
    # expected dtype as a rudimentary form of validation:
    expected_dtype = {
        "region": np.str,
        "diag": np.int64,
        "n_valid": np.int64,
        "count.sum": np.float64,
        exp_summary_name: np.float64,
    }

    # use 'usecols' as a rudimentary form of validation,
    # and dtype. Keep 'comment' and 'verbose' - explicit,
    # as we may use them later:
    cvd = pd.read_csv(
        expected_path,
        usecols=expected_columns,
        dtype=expected_dtype,
        comment=None,
        sep='\t',
        verbose=False,
    )

    # name of the column with Probability of contacts is
    # based on the name of the column  with the diagonal-summary
    # stats in the input expected DataFrame:
    exp_summary_base, *_ = exp_summary_name.split(".")
    Pc_name = f"{exp_summary_base}.avg"

    lb_cvd, lb_slopes, lb_distbins = expected.logbin_expected(
        cvd,
        summary_name=exp_summary_name,
        bins_per_order_magnitude=bins_per_order_magnitude,
        bin_layout=bin_layout,
        min_nvalid=min_nvalid,
        min_count=min_count
    )
    # combine Probabilities of contact for the regions:
    lb_cvd_agg, lb_slopes_agg = expected.combine_binned_expected(
        lb_cvd,
        Pc_name=Pc_name,
        binned_exp_slope=lb_slopes,
        spread_funcs=spread_funcs,
        spread_funcs_slope=spread_funcs_slope
    )
    if resolution is not None:
        lb_cvd_agg['s_bp'] = lb_cvd_agg['diag.avg'] * resolution
        lb_slopes_agg['s_bp'] = lb_slopes_agg['diag.avg'] * resolution

    lb_cvd_agg.to_csv(
        f'{output_prefix}.log.tsv',
        sep="\t",
        index=False,
        na_rep="nan",
    )
    lb_cvd_agg.to_csv(
        f'{output_prefix}.der.tsv',
        sep="\t",
        index=False,
        na_rep="nan",
    )
