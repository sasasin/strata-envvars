# `DS4_ATTN_MX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 版 DS4 の sparse attention で、packed KV（`ckv_fmt == 2`）向けの matrix-unit kernel を選ぶかどうかを制御します。既定値は matrix-unit kernel を選ぶ `1` です。値が厳密に `2` の場合は、その kernel の後に scalar kernel も同じ入力で実行し、出力差を stderr に記録します。

この分岐は Metal 実装 `metal/src/engine/ds4_finish.cpp` の `sparse_attn()` にあります。Metal build は macOS のみを対象とし、同ファイルは `strata_ds4` に組み込まれます（`metal/CMakeLists.txt:16-18,135-165`）。共通 DS4 attention 呼び出しから Metal 実装が先に呼ばれます（`src/dsv41/ds4_kernels.cu:2425-2436`）。

## 値と判定

値は `std::getenv()` で取得し、未設定なら `1`、設定済みなら `std::atoi()` で整数に変換します。`atoi` のため文字列全体の厳密な検証はなく、先頭の空白と符号の後の数字列を変換し、数字以降の文字は変換に含めません。数字に変換できない文字列（空文字を含む）は `0` になります。

| 環境値 | 判定結果 | 動作（他の条件も満たす場合） |
|---|---:|---|
| 未設定 | `1` | matrix-unit kernel |
| `0`、空文字、数字に変換できない文字列 | `0` | scalar kernel |
| `2`（または `2x`、`+2` など `atoi` が `2` と読む値） | `2` | matrix-unit kernel の後に scalar 比較を実行 |
| その他の非ゼロ整数（負数を含む） | その整数 | matrix-unit kernel。比較は行わない |

変換後の値が `0` かどうかだけで kernel 選択を切り替えます。数値範囲の検証や clamp はありません。変数が未設定かどうかではなく、変換後の整数値で選択します。実装位置: `metal/src/engine/ds4_finish.cpp:1223-1224,1277-1300`。

## 有効になる条件

matrix-unit kernel を選ぶ条件は、`ckv_fmt == 2`、head grouping の `G == 8`、かつ `DS4_ATTN_MX` の変換結果が `0` 以外であることです。`G` は head 数と `T` から同関数内で決まり、head 数が 8 の倍数でない場合や `(heads / G) * T < 64` の場合は 8 より小さくされるため、値が非ゼロでも matrix-unit kernel に切り替わらないことがあります（`metal/src/engine/ds4_finish.cpp:1219-1224`）。

packed KV でも上記条件を満たさない場合は `G` に応じた scalar kernel（`ds4_sparse_attn_g8/g4/g2/g1`）を使います。`ckv_fmt != 2` の BF16 KV は `ds4_sparse_attn_bf16` を使い、この変数の値で選択は変わりません（`metal/src/engine/ds4_finish.cpp:1238-1241`）。モデル側では MTP 経路が BF16 KV を指定しています（`src/dsv41/ds4_model.cu:10256-10263`）。

## 実行時の詳細

`attn_mode` は `sparse_attn()` 内の function-local `static const int` です。入力形式などの早期検査と Metal context の `ensure()` を通過し、関数が初めてこの判定に到達した時に読み取られ、その後の呼び出しでも同じ値が使われます。プロセス実行中に環境値を変更しても再評価されません。CLI 引数や他の環境変数との上書き処理は、この判定箇所にはありません（`metal/src/engine/ds4_finish.cpp:1151-1160,1223`）。

選ばれた pipeline が利用できない場合は `dsv41 metal: sparse_attn pipeline %s unavailable` を stderr に出し、関数は `false` を返します。共通側は Metal 実装が `true` を返せばそこで終了し、`false` の場合は後続の backend kernel 経路へ進みます（`metal/src/engine/ds4_finish.cpp:1242-1257`; `src/dsv41/ds4_kernels.cu:2432-2439`）。入力形式未対応や `gen == 0 && T > 16` もそれぞれ stderr に理由を出して `false` を返します（`metal/src/engine/ds4_finish.cpp:1153-1159`）。

変換結果が `2` で matrix-unit kernel が選ばれた場合、scalar `ds4_sparse_attn_g8` を追加 dispatch し、完了後に両出力の最大絶対差と RMS 相対差を計算します。呼び出し回数 1、51、101、… で `attn mx vs scalar: ...` を stderr に出し、累積最大 RMS 相対差も表示します。この比較は診断用で、通常出力 `out` は先に実行した matrix-unit kernel の結果のままです。比較用 pipeline が取得できない場合は比較を省いて `true` を返します（`metal/src/engine/ds4_finish.cpp:1277-1302`）。

## 根拠

- `metal/src/engine/ds4_finish.cpp:1151-1160` — sparse attention の入口、入力検査、Metal context 初期化。
- `metal/src/engine/ds4_finish.cpp:1219-1241` — `G` の決定、環境値の parse、kernel 選択。
- `metal/src/engine/ds4_finish.cpp:1242-1257` — pipeline 選択と失敗ログ。
- `metal/src/engine/ds4_finish.cpp:1277-1302` — mode `2` の scalar 比較と観測ログ。
- `src/dsv41/ds4_kernels.cu:2425-2439`、`src/dsv41/ds4_model.cu:10256-10263` — 共通 DS4 からの呼び出しと BF16 経路。
- `metal/CMakeLists.txt:16-18,135-165` — macOS 条件および `strata_ds4` の構成。
- `docs/DETAILS.md` — `DS4_ATTN_MX` に関する記載は確認できませんでした。
