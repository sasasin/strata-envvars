# `STRATA_ATTN_LANECELL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。Strata 所有ソースを対象とし、外部ライブラリの挙動は含めない。

## 役割

QSA decode attention の score 計算で、各 GPU thread が attention cell を担当して複数 query head の score を計算する lane-cell kernel を選びます。既定の warp-scoring kernel と同じ演算順序で score を作る実装です。CUDA/HIP 系ソースでは環境値が `1` で始まる場合に選択され、SYCL 系では環境値に加えて Intel Battlemage の大きな query batch に対する既定選択があります。GPU attention の計算経路に関する設定で、CLI 引数はありません。

## 値と判定

| 実装箇所 | unset / 空文字 | 設定値の判定 | 結果 |
|---|---|---|---|
| CUDA/HIP `qsa_decode_attn.cu` | off（後述の AMD architecture defaults が設定する場合を除く） | 先頭文字だけを見る | 先頭が `1` なら on。それ以外は off（`1abc` は on、`true` / `2` は off） |
| SYCL `qsa_decode_attn.dp.cpp` の batch | 自動判定へ | 空でない値を `atoi` で整数化 | 正数なら on、0 なら off、負数なら自動判定へ（`1abc` は on、`junk` は off） |
| SYCL `qsa_decode_attn.dp.cpp` の batch-rows | 明示 on を要求しない | 空でない値を `atoi` で整数化 | 結果がちょうど 1 の場合だけ per-row 経路を要求。それ以外は要求しない |

CUDA/HIP の判定は `v[0] == '1'` のみで、数値変換、空白除去、大文字小文字変換はありません。SYCL の `atoi` は文字列全体の妥当性を検査しません。明示値の parse 結果は初回参照時に `static` へ保存され、プロセス稼働中の環境変更は再評価されません（`src/kernels/cuda/qsa_decode_attn.cu:914-918,1151-1152`; `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:678-685,897-901`）。

## 有効になる条件

- CUDA/HIP では QSA の chunked batch attention または slots attention がこの kernel launcher を使う経路で有効です。batch launcher は環境値が on のとき KV format ごとの `attn_chunk_kernel<M, true>` を起動し、slots launcher も同じ lane-cell specialization を選びます（`src/kernels/cuda/qsa_decode_attn.cu:963-985,1072-1118`）。
- CUDA/HIP の `STRATA_ATTN_LANECELL` 単独には architecture による自動 on はありません。ただし HIP build の起動処理は gfx12 (RDNA4) と gfx1151 (Strix Halo) で、未設定の `STRATA_ATTN_LANECELL` を `1` にする architecture defaults を適用します。gfx1151 の Windows/Linux 共通表と gfx12 の表に含まれます。`STRATA_DEFAULTS=026` のとき gfx12 表はこの decode set を追加しませんが、gfx1151 表の対象 switch は残ります。`STRATA_GFX12_DEFAULTS` または `STRATA_GFX1151_DEFAULTS` が先頭文字 `0` なら該当表全体を追加しません（`src/core/arch_defaults.cpp:13-57,69-80`; `include/strata/core/defaults_026.hpp:1-9,25-34`; `src/program/generate.cpp:3383-3400`）。
- HIP の setup 設定では、opt-in の gfx1103 / gfx1150 向け profile に `STRATA_ATTN_LANECELL=1` が config の `env` として書かれます。engine 起動時には `child_env()` が親環境を複製した後に config の `env` を上書きするため、その profile 値が渡ります（`setup.py:3674-3697,10316-10327`; `serve/server.py:3747-3763`）。
- AMD architecture default は変数が何らかの値（空文字を含む）で既に設定されていれば上書きしません。そのため明示設定は table default に優先します。`setenv(..., overwrite=0)` でも既存値を保持します（`src/core/arch_defaults.cpp:167-189`）。setup profile の `env` は `child_env()` で親環境に後から重ねる設定です（`serve/server.py:3750,3759-3760`）。
- SYCL の batch 関数では、unset / 空文字の自動判定時に `n_q >= 16` かつ実行デバイスの世代が Battlemage の場合に lane-cell を選び、それ以外では選びません。明示的な非空値はこの自動判定に優先します（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:671-685`）。
- SYCL batch-rows 関数は別判定です。`STRATA_ATTN_LANECELL` の整数値が `1` の場合は per-row で batch 関数へ戻り、そうでなければ rows kernel を使います。ここで unset の Battlemage 自動判定は行いません（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:888-922`）。
- `qsa_decode_attn_slots()` が未対応 geometry / buffer を見つけると stderr にエラーを出して `exit(1)` します。query slot 数超過や KV mode 不一致など、launcher が `false` を返す条件では呼び出し側の別経路になります。これらは lane-cell 値の無効値エラーではありません（`src/kernels/cuda/qsa_decode_attn.cu:1072-1087,1120-1127`）。

## 実行時の詳細

lane-cell kernel では thread `t` が cell `t % 64` と head 群 `t / 64` を担当し、各 head の 8 要素部分和と、その後の butterfly reduction を計算します。CUDA/HIP 実装は `LANE_CELL=true` の template specialization を起動し、SYCL にも同じ score 計算の specialization があります。通常の経路は warp ごとに複数 cell を処理する構成です（`src/kernels/cuda/qsa_decode_attn.cu:172-208`; `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:185-210`）。

CUDA/HIP kernel の値は `lane_cell_attn()` および rows 用 `static` 初期化時に読むため、各読み取り箇所で一度だけ評価されます。SYCL batch / batch-rows もそれぞれの関数内の `static` 値を使います。環境変数を変更しても、該当 static が初期化された後の同一プロセスには反映されません。AMD の architecture defaults は kernel が設定値を読む前、引数処理後の起動時に環境へ値を設定します（`src/program/generate.cpp:3383-3400`; `src/core/arch_defaults.cpp:175-189`）。

Strata のコードに lane-cell 選択そのものを通知する専用ログや、環境値の無効値に対する警告は見当たりません。AMD architecture defaults が新たに環境値を設定した場合は `strata: gfx12 (RDNA4): ... exact speed switches on by default ...` または `strata: gfx1151 (Strix Halo): ...` の一行に switch 名 `ATTN_LANECELL` が出ます（`src/core/arch_defaults.cpp:182-189`）。不正な geometry 等の失敗は上記のとおり別途 stderr と終了で観測されます。

## 根拠

- CUDA/HIP の値判定、kernel 選択、slots 経路: `src/kernels/cuda/qsa_decode_attn.cu:914-918,963-985,1072-1127,1149-1172`。
- SYCL の query-count / device-generation default と batch-rows の例外: `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:671-685,888-922`。
- AMD architecture defaults と既存値の優先: `src/core/arch_defaults.cpp:25-57,69-80,167-189`; 起動時適用 `src/program/generate.cpp:3383-3400`。
- opt-in profile の設定と子プロセス環境への適用: `setup.py:3674-3697,10316-10327`; `serve/server.py:3747-3763`。
