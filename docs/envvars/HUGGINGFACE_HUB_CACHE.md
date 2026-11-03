# `HUGGINGFACE_HUB_CACHE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata の DFlash2 ドラフター取得処理が、Hugging Face Hub のキャッシュに既にあるピン留め済みスナップショットを探すときの候補ディレクトリの一つです。Strata はこの変数をライブラリへ転送したり、Hub のキャッシュ設定として使ったりしません。環境変数からパスを読み、対象ファイルが既に存在するかを調べます。

この参照は `strata_control/drafting_fetch.py` の `_hub_snapshots()` にあります。同関数は `ensure()` がまだ DFlash2 pack を持たず、通常のファイル一覧を使うときに呼ばれます。pack が既に利用可能な場合や `ensure(..., files=...)` でファイル一覧を渡した場合は、このキャッシュ探索経路に入りません（`strata_control/drafting_fetch.py:76-85,144-160`）。

## 値と判定

| 状態 | Strata の処理 |
|---|---|
| 未設定 | この変数からキャッシュ root を追加しない。 |
| 空文字 | `os.environ.get(name)` が偽となるため、未設定と同じく追加しない。 |
| 空でない値 | 値全体を `Path` に渡し、そのディレクトリを root に追加する。数値変換、trim、値域検証はしない。 |

空白だけの値も空でないため root として追加されます。相対パス、`~` を含む文字列、環境変数参照文字列の展開処理はこの箇所にありません。root の下に `models--incoai--Qwen3.8-Flash-Next-DFlash2/snapshots/<revision>` を組み立て、その snapshot 内の pinned ファイルを探します（`strata_control/drafting_fetch.py:76-85`）。

## 有効になる条件

- DFlash2 pack がまだ ready でなく、`ensure()` が通常の `drafting.FILES` を使う場合に探索します（`strata_control/drafting_fetch.py:149-160`）。
- `files` 引数が指定されている呼び出しでは Hugging Face cache roots を探索しません（`strata_control/drafting_fetch.py:159-160`）。
- 変数が空でない場合でも、組み立てた pinned snapshot 配下に必要なファイルがなければ再利用されません。各ファイルは通常のローカル `src` を先に、次にキャッシュ root の順で探し、存在・サイズ・SHA-256 が pinned 値と一致したものだけを採用します（`strata_control/drafting_fetch.py:88-100,159-160`）。
- 複数の root を同時に調べます。root の順序は `HF_HUB_CACHE`、`HUGGINGFACE_HUB_CACHE`、`HF_HOME/hub`、`~/.cache/huggingface/hub` です。したがって `HUGGINGFACE_HUB_CACHE` は専用の上書き優先設定ではなく、`HF_HUB_CACHE` の後に試す追加候補です（`strata_control/drafting_fetch.py:78-85`）。

## 実行時の詳細

`_hub_snapshots()` は呼び出しのたびに `os.environ` を読み、結果をキャッシュしません。`ensure()` で pack が未準備なら、まず `data_dir` 内の `src` を候補にし、その後にこの関数が返す snapshot paths を追加して `_present()` に渡します。ファイルごとに候補を順番に確認し、サイズと SHA-256 が pinned 値に一致した最初のものを再利用します。キャッシュ内のファイルを変更・削除する処理はこの探索にありません。必要ファイルの一部しか見つからず、オンライン確認にも失敗する場合は `DraftingError` を送出します（`strata_control/drafting_fetch.py:88-100,159-163`）。

この変数によるログ出力や独自の無効値エラーはありません。値が空ならこの変数由来の root は追加されず、その root が存在しない、または pinned snapshot が見つからない場合はこの候補からファイルを再利用しません。他の root も含めて必要なファイルが揃わなければ通常の取得手順へ進みます。実際の通信・pack 作成はキャッシュ探索の後段です（`strata_control/drafting_fetch.py:159-195`）。

## 根拠

- `strata_control/drafting_fetch.py:76-85` — `HF_HUB_CACHE` と `HUGGINGFACE_HUB_CACHE` の読み取り、`HF_HOME` と既定 root、snapshot path の構成。
- `strata_control/drafting_fetch.py:88-100` — 候補ファイルの存在・サイズ・SHA-256 検証と、候補順で最初に一致したファイルの採用。
- `strata_control/drafting_fetch.py:144-163` — pack ready の早期 return、`files` による探索省略、cache 探索後のオンライン確認と失敗経路。
- `strata_control/drafting_fetch.py:166-195` — 見つからなかったファイルのダウンロード、チェック、pack 作成とエラー経路。

