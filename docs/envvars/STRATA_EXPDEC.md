# `STRATA_EXPDEC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

GPU の `native_expert_grouped` が実行する routed expert の gate/up 計算について、対応する量子化形式・形状なら EXPDEC カーネルを選びます。このカーネルはグループの q8_1 activation を shared memory に置き、複数行をまとめて計算します。対象外の形式・形状では通常カーネルに戻ります。down 計算は別設定 `STRATA_EXPDEC_DOWN` が必要です。

実行時の選択箇所は `src/kernels/cuda/iq_kernels.cu` です。同ファイルは CUDA/HIP の GPU カーネルターゲットに含まれます（`CMakeLists.txt:412,456-502`）。一方、説明資料 `docs/EXPERTDEC.md:3` は「CUDA only」と記しています。現行のソース上では同じ GPU カーネル経路に判定と HIP 用アーキテクチャ既定値もあるため、同資料の backend 範囲の説明とは一致しません。ここではコードで確認できる選択条件を記し、性能測定値は一般化しません。

## 値と判定

`STRATA_EXPDEC` は `env_on("STRATA_EXPDEC")` で判定します。環境変数の文字列全体は parse せず、未設定でないこと、空文字でないこと、先頭文字が `0` でないことを見ます。

| 値 | 判定 |
|---|---|
| 未設定 | 判定時点の既定値に従う。通常は OFF。HIP gfx1200/gfx1201 のアーキテクチャ既定値が適用済みなら ON |
| 空文字 | OFF。設定済みなので、アーキテクチャ既定値による補完も抑止する |
| `0` または `0` 始まりの文字列 | OFF（例: `0`, `0abc`） |
| その他の非空文字列 | ON（例: `1`, `2`, `true`, `false`, ` 0`） |

数値変換、範囲検査、大文字小文字の正規化はありません。値が有効判定でも、後述の適用条件を満たさない呼び出しは通常カーネルを使います。

根拠: `src/kernels/cuda/iq_kernels.cu:3395-3398,4060-4062`。

## 有効になる条件

- `STRATA_EXPDEC` が ON で、旧 grouped kernels を選ぶ `STRATA_OLD_IQ_MMVQ` が ON でないこと。後者も同じ `env_on()` 判定です。
- 対象計算が `native_expert_grouped` の gate/up または down 経路に到達すること。EXPDEC は通常の grouped dispatch から呼ばれます。nibble layout の分岐では先に nibble kernel を選び、EXPDEC 判定には進みません。
- gate/up は量子化 type `16, 17, 18, 21, 22`、`n_embd == 32 * ED_XB`、`n_ff > 0` かつ `n_ff` が64の倍数のとき対応します。資料では主な形状を `n_embd 2560` と記載しています。
- down は `STRATA_EXPDEC_DOWN` が非ゼロで、type `42`（IQ4_NL）または `STRATA_EXPDEC_D20` も非ゼロの type `20`（Q2_0）であり、`n_ff == 32 * ED_HB`、`n_embd > 0` かつ128の倍数のとき対応します。既定では `STRATA_EXPDEC_DOWN=0` なので gate/up のみです。
- HIP では `src/program/generate.cpp` が GPU アーキテクチャを調べ、`apply_arch_defaults()` を engine が環境スイッチを初回評価する前に呼びます。`gfx1200` / `gfx1201` では `STRATA_GFX12_DEFAULTS` が `0` 始まりでなく、`STRATA_DEFAULTS=026` の旧表を使わない場合、表に `STRATA_EXPDEC=1` が含まれます。利用者が変数を何らかの値（空文字を含む）で設定済みなら、その値を保ちます。gfx1151 表にはこの変数がありません。CUDA 側の NVIDIA 既定表には同変数がありません。

根拠: `src/kernels/cuda/iq_kernels.cu:4151-4192,4077-4084`; `src/kernels/cuda/iq_kernels.cu:6323-6338,6404-6415,6484-6490`; `src/core/arch_defaults.cpp:27-53,55-57,167-180`; `src/program/generate.cpp:3383-3400,3445-3459`; `src/core/nv_defaults.cpp:23-80,82-92`。

## 実行時の詳細

`g_expdec` は初期値 `-1` で、`expdec_mode()` の最初の呼び出し時に環境値から決まり、以後プロセス内で保持されます。初回評価後に環境を書き換えても再読込されません。コード内 API `native_expert_set_expdec(int)` が呼ばれると環境判定結果を上書きできます。通常 engine の HIP アーキテクチャ既定値はこの初回評価より前に環境へ設定されます。CLI 引数による直接上書きは見つかりません。

EXPDEC が有効でも対応形式・形状でなければ `expdec_note()` がその role/type の初回に stderr へ `strata expdec: CUDA%d ... not covered: the default kernel runs` を出して通常カーネルを実行します。対応する場合も同関数が初回の role/type ごとに、選択した kernel、パラメーター、grid、graph capture の有無を stderr に記録します。down が設定不足などで無効なときは `expdec_down()` が false を返し、呼び出し元が通常 down kernel を使います。確認した経路には、この変数だけを理由とする警告や終了処理はありません。

根拠: `src/kernels/cuda/iq_kernels.cu:4060-4062,4120-4148,4151-4192,6216-6217`; HIP 既定値の適用順は `src/program/generate.cpp:3383-3400`。

## 資料との照合

`docs/EXPERTDEC.md:3,8-17,31-42` は opt-in、gate/up と down の分離、旧 kernels による無効化、初回ログについて説明しています。実装の値判定では `=1` だけでなく先頭が `0` でない任意の非空値が ON です。また、現行ソースは gfx12 HIP の既定値に `STRATA_EXPDEC=1` を含めるため、「未設定は常に OFF」「CUDA only」という資料の記述は、少なくともこのソース上の既定値・backend 範囲と一致しません。`docs/DETAILS.md:1052-1057,1430` にある性能値は特定構成の測定であり、ここでは一般的な効果として扱いません。
