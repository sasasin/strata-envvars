# `HF_HOME`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata Terminal は `HF_HOME` を Hugging Face の Hub cache 位置を探す手掛かりとして使います。DFlash2 の取得時には `$HF_HOME/hub` にある pinned revision のファイルを再利用候補に加えます。また、ユーザーの GGUF ファイルの隣に Strata 自身の準備データを書けるかを判定するときは、`HF_HOME` 以下を Hugging Face cache とみなし、その場所を Strata の書き込み先にしません。どちらも cache の場所を調べる用途であり、`HF_HOME` 自体を Strata の download 先にする設定ではありません。`terminal/strata_control/drafting_fetch.py:121-130,376-397`、`terminal/strata_control/discovery.py:455-479,484-497`。

## 値と判定

値は真偽値や数値に変換されず、パス文字列として使われます。どちらの読み取りも `get` 結果の truthiness を調べるため、未設定と空文字は同じく候補から外れます。`"0"`、`"false"`、空白だけの文字列も空ではないのでパスとして扱われ、大文字小文字の判定はありません。末尾の `/hub` は DFlash2 cache 検索でのみ追加されます。`drafting_fetch` は `~` を展開せず、相対パスは呼び出しプロセスの作業ディレクトリを基準に候補パスとして使います。一方 `discovery` は `expanduser()` と `resolve()` を試みます（`resolve()` の `OSError` は無視して比較を続行）。値の存在・パス形式・directory の事前検証や clamp はありません。`terminal/strata_control/drafting_fetch.py:121-130`、`terminal/strata_control/discovery.py:459-477`。

| 読み取り経路 | unset / 空文字 | 非空値の例 | 判定されない例 |
|---|---|---|---|
| DFlash2 cache 検索 | `$HF_HOME/hub` を候補に加えない | `/data/hf` → `/data/hf/hub`、`~/hf` → 相対的な `~/hf/hub` | 真偽値・数値としての無効値はない。`0`、`false`、空白もパスになる |
| ユーザー GGUF 隣の書き込み先判定 | `HF_HOME` root を追加しない | `/data/hf` 以下を cache 内と判定 | 真偽値・数値としての無効値はない。非空文字列は root パスとして比較する |

## 有効になる条件

- DFlash2 の既定取得処理で、ローカルの pack がまだ ready でなく、通常の pinned `files` を使う場合に Hub cache を調べます。`ensure()` に `files` が明示された内部呼び出しでは cache 検索自体を行いません。ready な pack が既にあれば `ensure()` は先に返るため、環境変数を読みません。`terminal/strata_control/drafting_fetch.py:376-392`。
- `$HF_HOME/hub/models--<org>--<name>/snapshots/<revision>/` の候補内にあるファイルが、対象ファイルごとに要求サイズと SHA-256 の両方に一致したときだけ再利用されます。部分一致なら見つかったファイルを使い、残りを取得します。HF cache 内のファイルを更新・削除・作成する処理ではありません。`terminal/strata_control/drafting_fetch.py:121-145,392-426`。
- cache の探索順は `src`、`HF_HUB_CACHE`、`HUGGINGFACE_HUB_CACHE`、`HF_HOME/hub`、`~/.cache/huggingface/hub` です。先行する各 root は対応環境変数が非空の場合だけ加わります。ファイルごとにこの順でサイズと hash を確認し、最初に一致したものを使います。したがって他 root に有効な一致ファイルがあれば `HF_HOME` は使われない場合があります。`terminal/strata_control/drafting_fetch.py:121-145,389-392`。
- 書き込み先判定は、ユーザーが指定したモデルファイルの位置から `models` の親を推定する経路に適用されます。推定パスまたはその `models/` が `HF_HOME` root 以下なら `writable_beside()` は `None` を返し、launch / app の既定フォルダーは通常の Strata data folder に戻ります。`terminal/strata_control/discovery.py:484-497`、`terminal/strata_cli/launch/runner.py:1514-1525`、`terminal/strata_cli/launch/app.py:311-326`。
- `strata launch` で `--data-dir` を明示すると、`beside_refused()` はこの cache 判定による通知対象を作らず、明示値を setup の `--data-dir` に渡します。`HF_HOME` は明示した data directory を拒否・書き換えません。`terminal/strata_cli/launch/runner.py:1548-1560,1399-1405`。

## 実行時の詳細

DFlash2 取得では `ensure()` が pack の ready 状態を先に確認します。未準備なら `_hub_snapshots()` がその時点の `os.environ` を読み、`HF_HOME` と他の cache root から revision snapshot の候補を組み立てます。値を `static` 等に保存する cache はなく、`ensure()` の呼び出しごとに評価します。候補ファイルは `_present()` がサイズと SHA-256 を検証し、揃わないファイルだけ `src` に download してから pack を作ります。`HF_HOME` 配下の候補に一致するファイルがなく、必要なファイルもなく、接続先が offline の場合は `OfflineError("There is no internet connection, so the DFlash2 drafter can't be downloaded now.")` を送出します。`terminal/strata_control/drafting_fetch.py:121-145,376-426`。

cache 保護側は `in_hf_cache()` が呼ばれるたびに現在の `os.environ` を参照します。`HF_HOME` root 以下かどうかは `Path.resolve()` 後の親子関係で判定します。DFlash2 側が `$HF_HOME/hub` を見るのに対し、こちらは `HF_HOME` 自体とその全 descendant を root にします。さらに `models--` で始まる path component も root 設定に関係なく cache と判定します。`HF_HOME` の値変更を処理中に監視するコードや子プロセスへ値を加工して渡すコードは、この読み取り箇所にはありません。`terminal/strata_control/discovery.py:455-479`。

## ログと測定値

推定したユーザー GGUF の隣が `HF_HOME` 配下で、Strata がそこを使わない場合、`strata launch` は「Your model files are used where they are. `<path>` is a Hugging Face download folder, so Strata keeps its own files (the prepared data and the picture reader) in `<data-dir>`.」という model 通知を出します（`<path>` と `<data-dir>` は実行時の値）。`HF_HOME` cache からファイルを再利用したこと自体を示す専用ログは、この読み取り経路にはありません。失敗時の DFlash2 offline 文言は前節のとおりです。`terminal/strata_cli/launch/runner.py:1710-1718`、`terminal/strata_control/drafting_fetch.py:392-396`。

## 根拠

- `terminal/strata_control/drafting_fetch.py:121-145` — Hub cache root の生成、優先順、ファイルのサイズ・SHA-256 検査。
- `terminal/strata_control/drafting_fetch.py:376-426` — ready pack の早期 return、cache 探索条件、offline 時の例外、見つからないファイルの取得と pack。
- `terminal/strata_control/discovery.py:455-497` — `HF_HOME` を含む cache 判定と、推定書き込み先を不採用にする処理。
- `terminal/strata_cli/launch/runner.py:1514-1560,1710-1718` — 推定 data directory の選択、拒否条件、利用者向け通知。
- `terminal/strata_cli/launch/runner.py:1399-1411`、`terminal/strata_cli/launch/app.py:311-326` — 明示 data directory と app の default folder の扱い。
