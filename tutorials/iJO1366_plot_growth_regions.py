import pandas as pd
import numpy as np
import bokeh.plotting as bp
from bokeh.models import Whisker, ColumnDataSource
from therme.io.json import load_json_model
import cobra

ec_cobra = cobra.io.load_json_model('iJO1366_with_xrefs.json')
# ec_cobra.reactions.ATPM.lower_bound = 0
growth_reaction_id = 'BIOMASS_Ec_iJO1366_WT_53p95M'

ecoli = load_json_model('models/iJO1366_t_489_256_bins_2018031.json')

uptake_range = pd.Series(list(range(100)))

def simulate(uptake, model):
    model.reactions.EX_glc__D_e.lower_bound = -1*uptake
    model.reactions.EX_glc__D_e.upper_bound = 0
    model.objective = growth_reaction_id
    model.objective.direction = 'max'
    try:
        sol = model.optimize()
    except Exception:
        return pd.Series([np.nan, np.nan])
    return pd.Series([sol.f, model.reactions.EX_glc__D_e.flux*-1])

try:
    me_data = pd.read_csv('outputs/benchmark_t489_256_bins.csv')
except FileNotFoundError:
    import json

    with open('iJO1366_128_bins_20180312.json', 'r') as fid:
        md = json.load(fid)
        fid.close()

    me_data = uptake_range.apply(simulate, args=[ecoli])
    me_data.columns = ['mu','uptake']

# End Data getter

def find_mu_error(mu):
    mu_steps = [x[0] for x in ecoli.mu_bins]
    mu_error = [abs(x-mu) for x in mu_steps]
    index = mu_error.index(min(mu_error))
    return pd.Series({'mu_lb':ecoli.mu_bins[index][1][0],
                      'mu_ub':ecoli.mu_bins[index][1][1]})

me_error = me_data['mu'].apply(find_mu_error)
aggregated_me_data = pd.concat([me_data, me_error], axis=1)

fba_data = uptake_range.apply(simulate, args = [ec_cobra])
fba_data.columns = ['mu','uptake']


me_source = ColumnDataSource(data=aggregated_me_data)

#---- Re-make ME-model figure with SNL v batch etc
p1 = bp.figure()

p1.xaxis.axis_label = 'glucose uptake (mmol.gDw/h)'
p1.yaxis.axis_label = 'growth rate (/h)'

# FBA Mu
p1.circle(x=fba_data['uptake'], y=fba_data['mu'], color = 'crimson', legend='FBA growth')

# tME Mu
p1.square(x=me_data['uptake'], y=me_data['mu'], legend='tME growth')
p1.add_layout(
    Whisker(source = me_source,
            base = 'uptake',
            lower = 'mu_lb',
            upper = 'mu_ub',
            )
)

## Systematic analysis

mu_max = max(me_data['mu'].dropna())
mask_snl = me_data['mu'] < mu_max*0.33
mask_pl  = me_data['mu'] > mu_max*0.99

fit1d = lambda x,y: np.poly1d(np.polyfit(x,y,1))

# fit_fba = fit1d(fba_data['uptake'], fba_data['mu'])
fit_snl = fit1d(me_data[mask_snl]['uptake'], me_data[mask_snl]['mu'])
fit_pl  = fit1d(me_data[mask_pl ]['uptake'], me_data[mask_pl ]['mu'])

p1.line(x=uptake_range,y=fit_snl(uptake_range),
        color = 'black', line_dash = 'dashed', legend = 'SNL fit')
p1.line(x=uptake_range,y=[me_data['mu'].iloc[-1]]*len(uptake_range),#fit_pl (uptake_range),
        color = 'black',line_dash = 'dotted', legend = 'Proteome Limited fit')

p1.legend.location = 'bottom_right'

bp.output_file("outputs/iJO1366_growth_regions.html")
bp.show(p1)