from pathlib import Path
from decimal import Decimal
import csv,io,json,pytest
from mary_workbench.calculations import calculate,analyze_table,render_table_csv

def test_exact_arithmetic():
    assert calculate('0.1 + 0.2')['exact']=='3/10'
    assert calculate('12 * (3 + 4)')['exact']=='84'
    assert calculate('solve: 2*x + 3 = 11')['solutions']==['4']
    assert calculate('solve: x^2 = 9')['solutions']==['-3','3']

@pytest.mark.parametrize('expression',["__import__('os')",'(1).__class__','True','1/0','log(0)','1e99999','2**100000','exp(exp(100))','[1,2]','x[0]'])
def test_bad_calculations_refuse(expression):
    with pytest.raises(ValueError):calculate(expression)

def table(tmp_path,body):
    p=tmp_path/'input.csv';p.write_text(body,encoding='utf-8');return p

def test_exact_sum_and_grouping(tmp_path):
    p=table(tmp_path,'Team,Amount\nA,0.1\nA,0.2\nB,2.5\n')
    assert analyze_table(p,'sum','Amount')['metrics']['value']=='2.8'
    assert analyze_table(p,'group_sum','Amount','Team')['rows']==[{'group':'A','value':'0.3'},{'group':'B','value':'2.5'}]

def test_count_text_is_supported(tmp_path):
    p=table(tmp_path,'Team,Item\nA,oak\nA,pine\nB,elm\n')
    assert analyze_table(p,'count','Item')['metrics']['count']==3
    assert analyze_table(p,'group_count','Item','Team')['rows']==[{'group':'A','value':2},{'group':'B','value':1}]

def test_formula_cannot_disappear_from_sum(tmp_path):
    from openpyxl import Workbook
    p=tmp_path/'formulas.xlsx';w=Workbook();s=w.active;s.append(['Team','Amount']);s.append(['A',2]);s.append(['A','=1+2']);w.save(p)
    with pytest.raises(ValueError):analyze_table(p,'sum','Amount')
    d=analyze_table(p);assert d['metrics']['Amount']['formulas']==1

def test_invalid_numeric_is_explicit(tmp_path):
    p=table(tmp_path,'Amount\n12\nunknown\n')
    with pytest.raises(ValueError):analyze_table(p,'sum','Amount')

def test_csv_overflow_is_not_truncated(tmp_path):
    p=table(tmp_path,'Amount\n'+'1\n'*50001)
    with pytest.raises(ValueError):analyze_table(p,'sum','Amount')

def test_csv_shape_refused(tmp_path):
    p=table(tmp_path,'A,B\n1,2,3\n')
    with pytest.raises(ValueError):analyze_table(p,'describe')

def test_missing_values_accounted(tmp_path):
    p=table(tmp_path,'A,B\nx,2\ny,\nz,3\n');r=analyze_table(p,'sum','B');assert r['metrics']['value']=='5';assert r['missing_rows']==[3]

def test_csv_export_string_injection_and_numeric_sign():
    result={'kind':'table','rows':[{'group':'=HYPERLINK("bad")','value':'-2.5'}]}
    rows=list(csv.reader(io.StringIO(render_table_csv(result))))
    assert rows[1][0].startswith("'=");assert rows[1][1]=='-2.5'
