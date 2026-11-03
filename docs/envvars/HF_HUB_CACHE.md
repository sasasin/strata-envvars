# `HF_HUB_CACHE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata Control が DFlash2 drafter を用意するとき、Hugging Face cache に既にある固定 revision のファイルを探すための cache root として参照します。見つけたファイルはサイズと SHA-256 を照合し、条件に合えばその場所から pack します。`HF_HUB_CACHE` は Strata のダウンロード先を変更しません。ダウンロードが必要なファイルは Strata のデータディレクトリ配下に保存されます。

この参照は通常の engine 起動や serve の engine 処理ではなく、明示的な `strata drafting fetch`、または launch が必要と判断した DFlash2 drafter の準備経路にあります（`strata_control/drafting_fetch.py:144-160`, `strata_cli/drafting_cmd.py:81-87,116-123`, `strata_cli/launch/runner.py:1581-1598`）。

## 値と判定

| 状態 | Strata の扱い |
|---|---|
| 未設定または空文字 | `os.environ.get(name)` が falsy となり、この変数から cache root を追加しない。 |
| 空でない値 | 値を加工せず `Path(value)` に渡し、cache root として追加する。相対パスも絶対化・検証せず、相対パスは実行時の作業ディレクトリ基準で候補に使われる。 |
| 存在しない root、候補ファイルがない、サイズまたは SHA-256 が違う | その候補を採用せず、次の root を調べる。候補の stat/hash で `OSError` が起きた場合も次へ進む。 |

値を真偽値や数値には変換しません。たとえば `HF_HUB_CACHE=0` も空でないパス文字列として扱います。空白の trim、パスの展開、境界値検査、無効値エラーはありません。

検索 root の順番は `HF_HUB_CACHE`、`HUGGINGFACE_HUB_CACHE`、`HF_HOME/hub`、`~/.cache/huggingface/hub` です。`HF_HUB_CACHE` が有効な候補を持てば同じファイルについて後続 root より先に使われます。どれも未設定なら、後二つの既定 root は引き続き検索されます。別の root に有効な候補があれば、先行 root の候補が無効でもそちらを使えます（`strata_control/drafting_fetch.py:76-85,88-100`）。

## 有効になる条件

- `ensure()` が、pack がまだ ready でない状態で実行されること。pack が既に ready なら早期 return し、cache snapshot は調べません（`strata_control/drafting_fetch.py:144-160`）。
- 実データの通常経路であること。テスト用に `files` を渡した場合は Hugging Face cache 探索を省きます（`strata_control/drafting_fetch.py:159-160`）。
- DFlash2 pack が必要な経路であること。CLI の fetch は `ensure()` を呼び、launch は `drafting.needs_pack(...)` のときだけ `ensure()` に進みます（`strata_cli/drafting_cmd.py:84-87,116-118`, `strata_cli/launch/runner.py:1587-1598`）。

Strata のデータディレクトリ内の `src` が Hugging Face cache より先に調べられます。cache 側の全ファイルが見つかり、検証に通った場合はネットワーク確認とダウンロードを省きます。不足ファイルが残る場合は不足分を Strata 側の `src` にダウンロードします。通信不能で不足が残る場合は `DraftingError` になります（`strata_control/drafting_fetch.py:157-178`）。

## 実行時の詳細

環境変数はモジュール import 時ではなく、`ensure()` の未準備 pack 経路で `_hub_snapshots()` が呼ばれた時に読みます。値は関数呼び出しごとに参照され、Strata 内に static/global cache されません。同じ `ensure()` 実行中は root 一覧を一度作り、その一覧を使ってファイルを探します（`strata_control/drafting_fetch.py:76-85,144-160`）。

探索対象は `strata_control/drafting.py` に固定された `incoai/Qwen3.8-Flash-Next-DFlash2` の revision `a22a1744e85c17364dcc54a6a420af7135d4c7f6` の snapshot 内です。該当 repo の snapshot directory を組み立て、各必要ファイルを `is_file()`、期待サイズ、SHA-256 の順で確認します（`strata_control/drafting.py:192-196`, `strata_control/drafting_fetch.py:76-100`）。一致したファイルはその場で読み pack に使い、Hugging Face cache 内のファイルを変更・削除しません（`strata_control/drafting_fetch.py:160,181-190,196-202`）。

`HF_HUB_CACHE` 固有の警告やログはありません。launch 経路では fetch の進捗を model event として通知し、失敗時は警告 notice を出して MTP（または drafter なし）で続行します。直接の `strata drafting fetch` では失敗メッセージを stderr に出し、終了コード 5 を返します（`strata_cli/launch/runner.py:1592-1606`, `strata_cli/drafting_cmd.py:116-123`）。これらは cache hit/miss の専用ログではありません。

## 根拠

- `strata_control/drafting_fetch.py:76-85` — `HF_HUB_CACHE`、別名、`HF_HOME`、既定 root の読み取りと順序。
- `strata_control/drafting_fetch.py:88-100` — 候補ファイルの存在・サイズ・SHA-256 検証、`OSError` 時の継続。
- `strata_control/drafting_fetch.py:144-178,181-202` — 読み取り経路、cache hit の利用、不足時の download と pack。
- `strata_control/drafting.py:192-196` — 探索する repo、固定 revision、対象ファイル定義。
- `strata_cli/drafting_cmd.py:81-87,103-123` — `strata drafting fetch` の必要性判定と失敗時の出力・終了コード。
- `strata_cli/launch/runner.py:1581-1606,2641-2648` — launch からの呼び出し条件、進捗・失敗時の fallback。
