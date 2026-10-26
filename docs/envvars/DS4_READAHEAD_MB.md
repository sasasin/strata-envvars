# `DS4_READAHEAD_MB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。Strata 所有ソースを対象とし、外部ライブラリや OS 内部の先読み動作は対象外。

## 役割

DS4 モデルの実行で、CPU lane の expert をモデルファイルからその場で読む経路において、expert のコピーより前にファイル範囲へ `WILLNEED` の助言を出す量を制限します。上限の単位は MiB 相当（入力値に 1,048,576 を乗算）です。既定値は `2048` です。

これはコピー量、GPU のリング容量、あるいは OS が実際にキャッシュした量を制限する設定ではありません。先読みスレッドが未処理として数えている expert 領域の概算バイト数を制御します。参照: `src/dsv41/ds4_model.cu:3160-3196`。

## 値と判定

`read_ahead()` 内の関数局所 `static const double` を最初に初期化するときに値を取得します。環境変数が未設定なら `2048.0`、設定済みなら `std::atof()` の戻り値を使い、さらに `1048576.0` を掛けます。したがって明示的な空文字や数値として解釈できない文字列は通常 `atof` により 0 になります。数値の後ろに文字があっても、数値として読める先頭部分が使われます（例: `12MB` は 12 として解釈）。文字列全体の妥当性検査、整数化、clamp はありません。

| 環境変数 | 上限 `cap` | 効果 |
|---|---:|---|
| unset | 2048 MiB | `ahead > cap` の間、先読みを止めて 500 µs 休止する |
| `0`、空文字、非数値文字列 | 0 MiB | 先読み依頼済み量が正になるたびに待ち、完了位置の更新後に再開する |
| 正数（例: `512`, `1.5`） | 値 × 1 MiB | 未処理量が上限を超えると、完了位置が進むまで新たな助言を止める |
| 負数 | 負の上限 | `ahead` の初期値 0 が既に上限を超えるため、この関数は先読み助言を出さず 500 µs 間隔で待つ。停止フラグが立つと終了する |

`atof` は数値の完全一致を要求しません。たとえば `12junk` は 12、`junk12` は 0 になります。NaN/無限大などの特殊表記も `atof` の変換結果に従い、コード側で排除しません。`cap` が NaN の場合、比較式 `ahead > cap` は偽となるため上限待ちは発生しません。

## 有効になる条件

- DS4 の `run_dev_chunks()` で、その device のストリーミング batch が存在し、`file_experts` が true のときにだけ先読みスレッドを作成します（`src/dsv41/ds4_model.cu:7650-7664`）。
- `file_experts` は GGUF パックなら true です。非 GGUF では `--mmap-experts` の明示値、または GPU に収まらない expert とホスト RAM の見積もりによって決まります（`src/dsv41/ds4_model.cu:1953-1974`）。そのため、GGUF を使う場合も実行時に stream batch がなければ環境変数は参照されません。
- batch は run の各対象 layer にある `host_list` の expert を `B` 個ずつ並べたものです。`B` は少なくとも 1 で、ring の大きさと `Chunk::kParts` から決まります（`src/dsv41/ds4_model.cu:7603-7656`）。GPU 側で保持している expert 全体や RAM 上にある expert の全体を先読み対象にするものではありません。
- Windows では `os::advise()` は引数を使わず何もしません。したがって先読みスレッドと上限計算は動きますが、Strata から `posix_fadvise` 相当の助言は出ません（`src/dsv41/ds4_os.hpp:297-304`）。非 Windows では `POSIX_FADV_WILLNEED` を呼びます。

## 実行時の詳細

`read_ahead()` は batch を layer 順に見て、各 expert のファイル範囲に対して助言し、範囲サイズを `ahead` に加算します。通常形式では `region_file / region_off / region_bytes`、MXFP4 では3つのファイル領域を助言しますが、上限計算へ加えるサイズは expert 1個分の `l0.blob` です。copy mode で MXFP4 expert が RAM に存在する場合はその expert の助言・加算を省略します（`src/dsv41/ds4_model.cu:3178-3196`）。

コピー側 `copy_ahead()` は expert の CUDA 転送を投入した後に `S.done` を進めます。先読みスレッドは `issued` queue の batch 番号が `done` より小さくなった分のサイズを `ahead` から引きます。したがって「未処理」は GPU 転送の完了イベントを直接追う量ではなく、コピー側が投入済みとした batch 位置に基づきます（`src/dsv41/ds4_model.cu:3166-3175,3194-3196,3198-3236`）。

`cap` は関数局所 static なので、プロセス内の最初の `read_ahead()` 呼び出しで一度評価され、その後の環境変更は反映されません。run 終了時には `Join` が停止フラグを立て、先読み thread を join します（`src/dsv41/ds4_model.cu:7654-7664`）。診断ログや設定値の出力はこの変数に関して見つかりません。

## 文書との照合

`docs/DETAILS.md` の Linux file tier 節には、GGUF をその場で読むときの別の機能（zero-copy、I/O prefetch、decode gate）と、一般的な `STRATA_READ_AHEAD` の説明がありますが、`DS4_READAHEAD_MB` の記載はありません（`docs/DETAILS.md:261-279`）。この調査では性能値を示す資料も確認できませんでした。

## 根拠

- `src/dsv41/ds4_model.cu:1953-1974` — `file_experts` の決定条件。
- `src/dsv41/ds4_model.cu:3150-3197` — `Streamer`、上限の parse、batch ごとの先読みとバイト計数。
- `src/dsv41/ds4_model.cu:3198-3236` — copy batch 投入と `S.done` の更新。
- `src/dsv41/ds4_model.cu:7603-7664` — batch の作成、先読み thread の起動と終了。
- `src/dsv41/ds4_os.hpp:297-304` — Windows no-op と非 Windows `posix_fadvise` の分岐。
