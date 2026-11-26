# `STRATA_MANIFEST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

診断用の JSON 出力先を指定する。Strata エンジンは選択された engine / budget / 実行経路と、ロードした tensor 形式などを `<指定パス>` に記録する。Terminal の all-cards split engine 判定は、判定内容を `<指定パス>.launch.json` に記録する。どちらも診断情報であり、値によって engine の選択や計算経路そのものを変更しない。エンジン側の記録は `engine/include/strata/core/run_manifest.hpp:1-18`、Terminal 側の記録は `terminal/strata_control/split_engine.py:542-564`。

## 値と判定

| 読み取り箇所 | 未設定 | 空文字 | 設定値の判定 |
|---|---|---|---|
| C++ エンジン | 無効。manifest 呼び出しは何もしない | 無効。`getenv` の結果をそのまま文字列にし、空なら `enabled()` が false | 空でない文字列をそのまま出力ファイル名として使う。`1` などのフラグ値への変換、trim、形式検査はない。`0`、`false`、空白だけの値も空でなければ有効 |
| Terminal の Python 判定 | 無効 | 無効。`if not target` で返る | 空でない文字列を出力先の基底名として使う。値の正規化・形式検査はない。`0`、`false`、空白だけも有効 |

C++ は `std::getenv("STRATA_MANIFEST")` が返すポインタを空文字列に置き換えず `std::string` に保存し、`file_.empty()` だけで有効性を判定する（`engine/include/strata/core/run_manifest.hpp:43-47,185-193`）。Python は `.get()` の返値の真偽だけを見ている（`terminal/strata_control/split_engine.py:542-550`）。数値境界はなく、CLI 引数や別の環境変数がこの出力先を上書きする処理もない。

## 有効になる条件

- **C++ エンジン:** エンジンプロセスの環境に空でない値があり、manifest を使うコード経路が含まれていること。値はエンジンの初回 manifest API 呼び出し時に読み込まれる（関数内 `static Manifest`）。`generate.cpp` は記録を `ready` 時点に書き出し、該当する情報が追加されればリクエスト間にも再出力する（`engine/include/strata/core/run_manifest.hpp:185-193`; `engine/src/program/generate.cpp:16347,18402-18404`）。
- **Terminal の launch 判定:** Terminal の `apply_split_engine` が split 判定に進み、`split_engine.apply_to_config` まで到達すること。split-engine mode が `off`、または native Strata family の場合は判定を呼ばず、launch 用 JSON も記録しない（`terminal/strata_cli/launch/runner.py:2241-2247`; `terminal/strata_control/split_engine.py:522-530`）。モデルやカード等の条件で split を採用しない判定でも、`apply_to_config` が完了すれば判定記録の対象になる。
- C++ の記録項目は CUDA/HIP 等の実際に通ったロード・生成経路に依存する。例えば dense tensor と head の記録は、それぞれのロード処理で manifest が有効な場合に追加される（`engine/src/core/native_dense.cpp:517-528,661-662`; `engine/src/core/native_head.cpp:281-289`）。MMQ の prefill 判定項目も、その plan 生成時に追加される（`engine/src/prefill/prefill.cpp:2043-2046,2082-2097`）。
- `--split-engine` や `STRATA_SPLIT_ENGINE` は Terminal が split 判定を行うかを決める別設定であり、`STRATA_MANIFEST` の有効性・出力先を変えない（`terminal/strata_control/split_engine.py:435-448,522-530`）。

## 実行時の詳細

C++ 側は `instance()` の関数内 static を初期化する最初の呼び出しで環境値を一度読み、プロセス中キャッシュする。その後環境を変更しても出力先は変わらない。`enabled()` はこの manifest のパスが空でないかを見る。各記録関数は無効なら即時 return し、有効なら engine / budget / path / tensor 情報をメモリ上に保持する（`engine/include/strata/core/run_manifest.hpp:41-82,185-193`）。

`ready` 時に stage が `ready` の JSON を `<path>` に書く。各リクエストループ開始時は dirty の場合だけ stage `request` で更新する。書き込みは `<path>.tmp` への出力後に rename し、Windows では rename が既存ファイルを置き換えられない場合に旧ファイルを削除して再試行する。初期 `ready` 出力自体は dirty でなくても呼ばれる（`engine/include/strata/core/run_manifest.hpp:84-114,117-153`; `engine/src/program/generate.cpp:16347,18402-18404`）。

Python 側は `record_launch_manifest` が呼ばれるたびに `os.environ` から読み、値の変更を次の launch 判定に反映する。明示的に空でない場合、`<path>.launch.json.tmp` に整形済み JSON を書いて `os.replace` する。エンジン本体の `<path>` と Terminal の `<path>.launch.json` は別ファイル（`terminal/strata_control/split_engine.py:542-564`）。

## ログと測定値

C++ が出力できない場合、stderr に `strata: STRATA_MANIFEST: cannot write <path>` を一度出す。失敗してもエンジン実行を止めず、失敗した書き込みは成功扱いにならない（`engine/include/strata/core/run_manifest.hpp:117-143`）。未設定・空文字では書き込みを行わず、この警告も出さない。Terminal 側は書き込み例外を握りつぶして `False` を返し、launch を止めず警告も出さない（`terminal/strata_control/split_engine.py:542-564`）。測定値は該当なし。

## 根拠

- `engine/include/strata/core/run_manifest.hpp:41-47,84-153,185-193`
- `engine/src/program/generate.cpp:16228-16258,16347,18402-18404`
- `engine/src/core/native_dense.cpp:517-528,661-662`
- `engine/src/core/native_head.cpp:281-289`
- `engine/src/prefill/prefill.cpp:2043-2046,2082-2097`
- `terminal/strata_cli/launch/runner.py:2241-2247,2266-2281`
- `terminal/strata_control/split_engine.py:435-448,516-530,542-564`
