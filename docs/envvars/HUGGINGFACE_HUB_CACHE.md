# `HUGGINGFACE_HUB_CACHE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata の Terminal が DFlash2 の元ファイルを準備するとき、既にある Hugging Face Hub のキャッシュを探す場所の一つとして読み取る。また、利用者自身の GGUF の隣に Strata 用データを置いてよいか判定するとき、そのパスを Hugging Face キャッシュとして扱う根拠にもする。どちらもキャッシュを読み取り専用で調べる処理であり、この変数はダウンロード先や Strata のデータフォルダーを直接指定しない。読み取りは `terminal/strata_control/drafting_fetch.py` の `_hub_snapshots()` と `terminal/strata_control/discovery.py` の `in_hf_cache()` にある。 (`terminal/strata_control/drafting_fetch.py:121-130`, `terminal/strata_control/discovery.py:455-479`)

## 値と判定

`os.environ.get("HUGGINGFACE_HUB_CACHE")` で値を取得する。`drafting_fetch._hub_snapshots()` では値が truthy の場合だけ `Path(value)` を検索 root に追加し、`discovery.in_hf_cache()` も falsey 値を飛ばす。空文字と未設定は同じく root として使われない。`"0"`、`"false"`、空白だけの文字列なども特別な真偽値・数値として parse せず、空でなければパス文字列として扱う。文字列の trim、存在確認、絶対パス化の明示的な処理は `_hub_snapshots()` にはない。`in_hf_cache()` 側は `expanduser()` と `resolve()` を試みる。 (`terminal/strata_control/drafting_fetch.py:123-130`, `terminal/strata_control/discovery.py:459-479`)

| 条件 | 未設定・空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| DFlash2 の通常 fetch (`files is None`) | この root は追加されない | 空でないパス。例: `/mnt/hf/hub`、`0`、`false` | 空文字。`0` や `false` は無効値ではなく、その名前のパスとして検索される |
| モデル隣接フォルダーの判定 | この root との包含関係は判定しない | 空でないパス。`expanduser()` と `resolve()` 後に調べる | 空文字。root 判定には使わない |

`HF_HUB_CACHE` と `HUGGINGFACE_HUB_CACHE` は同じ順序付き root リストに別々に追加され、片方が他方を上書きしない。さらに `HF_HOME/hub` と標準の `~/.cache/huggingface/hub`（隣接フォルダー判定では `HF_HOME` 自体と `~/.cache/huggingface`）も候補になる。値の優先設定ではなく、複数 root の順次検索・照合である。 (`terminal/strata_control/drafting_fetch.py:123-130`, `terminal/strata_control/discovery.py:467-479`)

## 有効になる条件

- DFlash2 の stock drafter が必要で、Strata の pack がまだ準備されていない場合に、`ensure()` が通常の固定ファイル一覧で呼ばれること。テスト用の `files` を明示した呼び出しでは Hugging Face cache の探索を行わない。 (`terminal/strata_control/drafting_fetch.py:376-392`)
- cache 内の対象は `drafting.REPO` と `drafting.REVISION` の snapshot ディレクトリーに限られる。各ファイルは存在に加え、固定サイズと SHA-256 が一致しなければ採用されない。条件不一致や `OSError` は候補不在として扱われ、別 root または通常ダウンロードへ進む。 (`terminal/strata_control/drafting_fetch.py:121-145`)
- 対象ファイルが揃わずネットワークにも到達できない場合は `OfflineError` になる。DFlash2 の準備自体は `strata drafting fetch`、Load（launch）、setup 経路から呼ばれる。Launch では DFlash2 が必要な場合だけ fetch を行い、失敗しても起動を止めず、MTP または drafter なしで続ける。 (`terminal/strata_control/drafting_fetch.py:388-396`, `terminal/strata_cli/drafting_cmd.py:281-301`, `terminal/strata_cli/launch/runner.py:2115-2129`, `terminal/strata_cli/launch/runner.py:2140-2158`, `terminal/setup.py:9079-9080`)
- 隣接データフォルダー判定では、GGUF のそばに推定したフォルダーまたはその `models` がこの root 内にあると、その場所を Strata の書き込み先として使わない。`models--` で始まるパス要素を含む場合も cache と判定する。この関数はモデル隣接の保存先を選ぶ Terminal の app / launch から呼ばれる。 (`terminal/strata_control/discovery.py:455-479`, `terminal/strata_control/discovery.py:484-497`, `terminal/strata_cli/launch/app.py:311-326`, `terminal/strata_cli/launch/runner.py:1514-1525`)

## 実行時の詳細

`_hub_snapshots()` は呼び出し時に環境を読み、各設定 root の下に `models--<org>--<repo>/snapshots/<pinned revision>` を組み立てる。探索順は、まず `ensure()` が渡す `<data>/dflash2/src`、次に `HF_HUB_CACHE`、`HUGGINGFACE_HUB_CACHE`、`HF_HOME/hub`、最後に標準 cache である。ファイルごとに最初にサイズとハッシュが合ったものを採用する。両方の環境変数が設定されていても両 root を調べる。 (`terminal/strata_control/drafting_fetch.py:121-145`, `terminal/strata_control/drafting_fetch.py:389-405`)

見つけた元ファイルは packer への入力に使われるが、cache 内のファイルは削除・移動されない。後片付けで削除するのは Strata 自身の `src` に置いたファイルだけである。作成される pack は Strata の data directory 配下に置かれる。変数値は関数呼び出しのたびに `os.environ` から参照され、Strata 側に static cache はない。 (`terminal/strata_control/drafting_fetch.py:392-420`, `terminal/strata_control/drafting_fetch.py:432-440`)

この探索は stock drafter の取得経路だけにある。既に pack があれば `ensure()` は早期 return する。モデルに合う tuned drafter の取得関数 `ensure_tuned()` は Hugging Face cache を検索せず、tuned 版が得られないとき stock 版へ fallback する経路では上記探索が行われる。 (`terminal/strata_control/drafting_fetch.py:294-320`, `terminal/strata_control/drafting_fetch.py:349-392`)

隣接フォルダー判定では、`HUGGINGFACE_HUB_CACHE` を含む cache root に GGUF の推定データフォルダーがある場合、Strata はそこを自身のファイル置き場にせず、通常の data directory を使う。明示的な `--data-dir` がある場合は `beside_refused()` がこの判定を省く。 (`terminal/strata_control/discovery.py:467-479`, `terminal/strata_control/discovery.py:484-497`, `terminal/strata_cli/launch/runner.py:1548-1560`)

## ログと測定値

環境変数専用のログや警告はない。隣接フォルダーが cache と判定されて保存先を切り替える場面では、launch の通知本文は `Your model files are used where they are. <path> is a Hugging Face download folder, so Strata keeps its own files (the prepared data and the picture reader) in <data_dir>.` となる（山括弧内は実際のパス）。cache に対象ファイルがなく offline の場合、明示 fetch は stderr に `strata: There is no internet connection, so the DFlash2 drafter can't be downloaded now.` を出して終了コード 5 を返す。Load は警告を表示して続行する。 (`terminal/strata_cli/launch/runner.py:1710-1718`, `terminal/strata_cli/drafting_cmd.py:290-301`, `terminal/strata_cli/launch/runner.py:2144-2158`)

## 根拠

- 環境値を cache root に加え、pinned snapshot の候補を作る: `terminal/strata_control/drafting_fetch.py:121-130`
- ファイルの存在・サイズ・SHA-256 検査と候補採用: `terminal/strata_control/drafting_fetch.py:133-145`
- fetch の cache 探索条件、ネットワーク fallback、pack 後の cleanup: `terminal/strata_control/drafting_fetch.py:376-442`
- cache path の判定と隣接フォルダーの書き込み先選択: `terminal/strata_control/discovery.py:455-497`
- launch の保存先拒否通知: `terminal/strata_cli/launch/runner.py:1710-1718`
- fetch CLI、Load、setup の呼び出し・失敗時の扱い: `terminal/strata_cli/drafting_cmd.py:281-301`, `terminal/strata_cli/launch/runner.py:2115-2158`, `terminal/setup.py:9079-9080`
- DFlash2 の測定条件や対象については `docs/DETAILS.md:1591-1595` に記載があるが、この環境変数の cache 解決規則は記載されていないため、規則は上記実装から記述した。
