# `STRATA_NO_PROMPT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata launch` が起動するモデルや preset を指定されず、TUI に入らない場合に、環境変数から「質問に答えられる端末」と判定する経路を止めます。値を読んでいるのは `strata_cli/launch/cmd.py` の `_can_ask()` だけです。この値はモデル実行エンジンやサーバーへ渡されず、プロセス起動時に設定されるものでもありません。

この変数は `strata launch` のあらゆる確認を抑止する設定ではありません。たとえば、モデル指定済みの起動でエンジンがなくモデルのダウンロード確認が発生する場合、その確認関数 `_ask_yes()` は `STRATA_NO_PROMPT` を調べません。stdin と stdout が両方 TTY なら質問し、どちらかが TTY でなければ「続行」を返します（`strata_cli/launch/cmd.py:521-532`, `strata_cli/launch/cmd.py:783-784`; `strata_cli/launch/runner.py:631-632,833-842`）。

## 値と判定

文字列の parse や数値変換はせず、Python の `os.environ.get()` の戻り値を真偽値として使います。

| `STRATA_NO_PROMPT` | `_can_ask()` での扱い |
|---|---|
| 未設定 | この変数単独では拒否しない。後続の `MSYSTEM`、`TERM_PROGRAM`、`TERM`、`WT_SESSION` のいずれかが空でない値かを調べる |
| 空文字 (`STRATA_NO_PROMPT=`) | 偽として扱い、この変数単独では拒否しない |
| 空でない任意の文字列 | 真として扱い、`_can_ask()` は偽を返す。`1`, `0`, `false`, 空白だけの値も同じ |

比較は大文字小文字を区別する値比較ではなく、Python の truthiness 判定です。`CI` も同じ `if` 条件で確認され、いずれかが空でなければ後続の端末環境変数より優先して「質問できない」とします。したがって `STRATA_NO_PROMPT` が空でない場合、`MSYSTEM` などが設定されていても打ち消されません。`stdin` が `None` または closed の場合は、環境変数を見る前に偽を返します（`strata_cli/launch/cmd.py:511-518`）。

## 有効になる条件

`run_launch()` で、起動対象の選択がなく (`have_choices` が偽)、TUI に入らず、`--plan` でもないときだけ `_can_ask()` が呼ばれます。`--no-tui`、JSON 出力 (`--output json`)、カタログ不在の場合は `_can_ask()` より先に同じ分岐を失敗させます。stdin と stdout が両方 TTY で TUI 条件を満たす場合は、この判定を通らず TUI を起動します（`strata_cli/launch/cmd.py:686-697,753-778`）。

モデル、preset などの選択がある起動では、この変数は `_can_ask()` を通じて参照されません。`--yes` と `--plan` も別の CLI 条件です。`--yes` は Runner のダウンロード確認を省く引数であり、環境変数の値を変更したり同じ判定を実行したりしません（`strata_cli/launch/cmd.py:142-145,781-784`; `strata_cli/launch/runner.py:631-632,833-842`）。OS や GPU backend による分岐はありません。

## 実行時の詳細

`_can_ask()` は呼び出しごとに `os.environ` を参照し、結果を static/global に cache しません。確認できる呼び出し箇所は `run_launch()` の「選択なし・非 TUI・非 plan」分岐の一つです。プロセス起動後の環境変更をこの呼び出し前に行えば、その時点の値が使われます。

`STRATA_NO_PROMPT` が空でないと `_can_ask()` は偽になり、該当の選択なし起動は失敗します。通常出力では stderr に次の案内を出し、終了コード `2` を返します: `` `strata launch` with no choices opens screens, and this is not a terminal (or --no-tui was given). Name what to start: --preset NAME, or --model NAME (strata launch --help has examples; --plan shows what would happen without changing anything). ``。JSON 出力の場合は同じ分岐が環境変数判定前に `machine` 条件で失敗し、標準出力にエラー JSON を出します（`strata_cli/launch/cmd.py:692-697,765-768`）。

変数を未設定または空文字にし、stdin が開いており、かつ `MSYSTEM` / `TERM_PROGRAM` / `TERM` / `WT_SESSION` のどれかが空でなければ `_can_ask()` は真になります。画面 UI が使えないときは plain questions 経路へ進み、そこで `Start it now? Models can be tens of GB to download. [Y/n] ` を尋ねます。EOF なら案内を stderr に出して終了コード `2`、否定回答なら `Nothing was changed.` を表示して `0` です（`strata_cli/launch/cmd.py:769-773,842-850`）。

## 根拠

- 環境値・空文字・`CI`・端末環境変数の判定: `strata_cli/launch/cmd.py:511-518`
- 呼び出し条件、TUI / plan / no-TUI / JSON の分岐、失敗文と終了コード: `strata_cli/launch/cmd.py:686-697,753-778`
- plain questions の表示、EOF と否定回答の結果: `strata_cli/launch/cmd.py:769-773,842-850`
- 別のダウンロード確認の扱い: `strata_cli/launch/cmd.py:521-532,781-784`; `strata_cli/launch/runner.py:631-632,833-842`
