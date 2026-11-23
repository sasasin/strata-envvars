# `STRATA_GDN_FUSE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の GDN prefill で、`gdn_conv` と chunked WMMA recurrence を一つの fused 経路で実行するかを選ぶ。`STRATA_GDN_FUSE` 自体が単独で経路を有効にするのではなく、`STRATA_GDN_CHUNKED` が 0 でないことも必要である。融合しない場合、呼び出し元は通常の `gdn_conv` と `gdn_recurrence`（KVA state-only 時は対応する state-only 経路）を呼ぶ。CUDA ビルドでは fused 関数が常に `false` を返し、環境変数を読まない。根拠: `engine/src/prefill/kernels.cu:2235-2242,3290-3299`、`engine/src/prefill/prefill.cpp:5196-5210,9334-9342`。

融合側は畳み込み出力を FP16 の `hbuf` に置き、畳み込みと履歴更新の後、prep と scan を起動する。gfx12 chunked scan は FP16 operands と FP32 accumulation/state を使うため、FP32 の別経路と数値精度の扱いは同一ではない。融合関数の成功後、呼び出し元は別々の畳み込み・再帰を重ねて呼ばない。根拠: `engine/src/prefill/gdn_wmma12.inc:3-9,45-46`、`engine/src/prefill/kernels.cu:2257-2272`、`engine/src/prefill/prefill.cpp:5203-5210`。

## 値と判定

初回の `gdn_fused_impl` 呼び出し時に `std::getenv` し、`STRATA_GDN_CHUNKED` のキャッシュ値が 0 でなく、かつ `STRATA_GDN_FUSE` が未設定または `std::atoi` の結果が 0 以外なら融合候補を有効にする。`atoi` は文字列全体の妥当性を検証せず、先頭から整数として読める部分を使う。根拠: `engine/src/prefill/kernels.cu:1894-1897,2238-2242`。

| `STRATA_GDN_FUSE` | 判定 | 例 |
|---|---|---|
| 未設定 | 有効側（既定で true）。ただし chunked 条件・GPU・長さなどを満たす必要がある | — |
| 空文字 | 無効 | `""` は `atoi` が 0 |
| 先頭の整数が 0 | 無効 | `0`, `0anything`, `true`, `false`, 空白だけ |
| 先頭の整数が非 0 | 有効側 | `1`, `-1`, `2tail`, ` 1` |

大文字小文字を比較する処理や、文字列全体・数値範囲を検査する処理はない。`STRATA_GDN_CHUNKED` は別にキャッシュされ、未設定または空文字は `-1`（未指定扱い）、それ以外は `atoi` の値となる。明示的な 0（または数値に変換できず 0 になる文字列）は融合を無効にする。根拠: `engine/src/prefill/kernels.cu:1894-1897,2238-2242`。

## 有効になる条件

- HIP ビルドであること。実際の通常 prefill 呼び出しも `STRATA_USE_HIP` で囲まれ、カーネル実装は `__HIPCC__` のときだけ fused 実装に入る。CUDA は読み取りも融合もしない。根拠: `engine/src/prefill/prefill.cpp:5196-5202,9334-9338`、`engine/src/prefill/kernels.cu:3290-3299`。
- 実行中デバイスが gfx12 であること。デバイス取得またはプロパティ取得に失敗した場合、gfx12 でない場合は融合関数が `false` を返す。マルチ GPU では呼び出し時のデバイスごとに gfx12 判定を更新する。根拠: `engine/src/prefill/kernels.cu:2245-2256`。
- `T >= 64`、かつ出力 stride `ld16` が 8 の倍数であること。`ld16 <= 0` は既定 stride に置換してから判定する。通常の呼び出しは `ld16=0` または prefill padding の stride を渡す。根拠: `engine/src/prefill/kernels.cu:1884,2242-2244,2255`、`engine/src/prefill/prefill.cpp:5195-5201`。
- `STRATA_GDN_CHUNKED` の条件を満たすこと。正の整数値なら自動の長さ gate は不要（ただし `T >= 64` は必要）。0 は融合を止める。未設定・空文字・負の整数は `gdn_chunked_env() < 0` として扱われ、`STRATA_GFX12_DEFAULTS` が先頭文字 `0` でなく、かつ `T >= STRATA_GDN_CHUNKED_MIN`（未設定・空文字なら 30000）が必要。`STRATA_GFX12_DEFAULTS=0` はこの自動有効化を止める。根拠: `engine/src/prefill/kernels.cu:1894-1901,2255-2256`。
- `STRATA_GDN_FUSE=1` だけでは不十分。たとえば `STRATA_GDN_CHUNKED=0` なら融合候補の時点で無効になり、融合なしの呼び出し元経路へ進む。逆に `STRATA_GDN_CHUNKED` が有効条件を満たし `STRATA_GDN_FUSE` が未設定なら融合が候補になる。根拠: `engine/src/prefill/kernels.cu:2238-2242,2255-2256`。
- `generate` は HIP 起動時に、Linux かつ可視 GPU がすべて gfx12 の場合、`STRATA_GDN_CHUNKED` が未設定なら `1` を設定する。利用者が設定した値（`0` を含む）は保つ。明示的な空文字も起動時既定値では上書きされないが、カーネル側では未指定扱いとなる。Windows ではこの既定値設定を呼ばない。したがってこの Linux 条件では `STRATA_GDN_FUSE` 未設定が初回から融合候補になる一方、長さ・デバイス・stride 条件は引き続き適用される。根拠: `engine/src/program/generate.cpp:4299-4315`、`engine/src/core/arch_defaults.cpp:278-290`。
- state-only の KVA 通常 prefill 呼び出しは融合関数を呼ばないため、この変数はその呼び出しで効かない。根拠: `engine/src/prefill/prefill.cpp:5196-5201`。

## 実行時の詳細

環境変数の判定 `on` は `gdn_fused_impl` 内の関数ローカル `static const bool`、chunked 値も別の関数ローカル static で初回評価後にキャッシュされる。同一プロセスでの環境変更は、それぞれの初回評価後には反映されない。`STRATA_GDN_CHUNKED_MIN` と `STRATA_GFX12_DEFAULTS` も `gdn_chunked_auto` 内で static cache される。根拠: `engine/src/prefill/kernels.cu:1894-1901,2238-2242`。

通常の GDN prefill は fused 関数を試し、`false` なら個別の畳み込みと recurrence にフォールバックする。fused 関数は gfx12 で畳み込み＋履歴更新、chunk prep、scan の各 kernel を起動し、成功時に `true` を返す。融合を無効にしても `STRATA_GDN_CHUNKED` による recurrence 側の別の chunked dispatch は独立して残り得る。つまり `STRATA_GDN_FUSE=0` は conv と recurrence の融合を止める指定であり、chunked recurrence 全体を止めるには `STRATA_GDN_CHUNKED=0` が必要。根拠: `engine/src/prefill/kernels.cu:2238-2272,3080-3091`、`engine/src/prefill/prefill.cpp:5203-5210`。

## ログと測定値

この変数の有効・無効や fallback 自体を示す専用ログは確認できない。融合 kernel の起動後に `check("gdn_conv_recurrence_fused")` が呼ばれ、CUDA/HIP エラーがあれば共通エラー処理 `strata::core::exit_device_error` へ渡す。条件不成立の `false` はエラーではなく呼び出し元の fallback となる。根拠: `engine/src/prefill/kernels.cu:2271-2272`、同 `:110-116`。

## 根拠

- 読み取り、値判定、cache: `engine/src/prefill/kernels.cu:1894-1901,2235-2242`
- gfx12・長さ・stride の適用条件、融合 kernel: `engine/src/prefill/kernels.cu:2242-2272`
- HIP 呼び出しと fallback: `engine/src/prefill/kernels.cu:3290-3299`、`engine/src/prefill/prefill.cpp:5196-5210,9334-9344`
- Linux の gfx12 起動時既定値: `engine/src/program/generate.cpp:4299-4315`、`engine/src/core/arch_defaults.cpp:278-290`
