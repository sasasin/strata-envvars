# `FNX_PF_GDN_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は split engine の GDN prompt chunked recurrence に診断比較を追加する開発・診断用フックです。設定されていると、chunked recurrence を実行する直前に row-by-row recurrence を同じ入力・初期状態で計算し、その後 chunked recurrence の出力と終端状態との差を stderr に出します。両方の計算結果を比較するだけで、差があっても判定・終了はしません。通常の推論経路の結果は、参照計算後に GDN 状態を復元してから chunked recurrence を実行するため、診断比較自体が出力を置き換える実装ではありません（`engine/src/split/src/kernels.cu:2034-2069`）。

## 値と判定

値の parse や文字列検査はなく、`std::getenv("FNX_PF_GDN_CHECK") != nullptr` の設定有無だけを見ます（`engine/src/split/src/kernels.cu:2034`）。

| ビルド / 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| split engine の CUDA / HIP chunked GDN 経路 | 比較を行わない | `1`、`0`、`true`、`false`、空文字、その他どの文字列でも有効（環境に存在すれば有効） | なし |

大文字小文字、空白、数値としての妥当性は調べません。たとえば `0` や空文字も設定ありとして診断を有効にします。`FNX_PF_GDN_CHUNK=0` で row-by-row 経路を選ぶ場合、この変数を読む診断分岐に入りません（`engine/src/split/src/kernels.cu:2018-2022,2034,2065-2068`）。

## 有効になる条件

- split engine の prompt prefill が非 attention 層の GDN を処理し、`gdn_prompt` に到達すること。呼び出しは `prefill.cu` の非 attention 層分岐にあります（`engine/src/split/src/prefill.cu:1651-1657`）。
- `FNX_PF_GDN_CHUNK` が未設定（既定で chunked）または `1` であること。`0` は chunked 経路を無効にし、その他の値は `FNX_PF_GDN_CHUNK: 0 or 1, not '…'` の例外になります（`engine/src/split/src/kernels.cu:2018-2022`）。
- NVIDIA では tensor-core GDN scan が先に成功して戻る場合、比較分岐は実行されません。対象 scan は CUDA、`FNX_ARCH >= 80` でのみコンパイルされ、実行時にも compute capability major が 8 以上、必要な shared memory が利用可能、scratch が確保済みであることなどを確認します。さらに `FNX_PFX_GDN_TC` の指定またはモデルの既定値が scan を選ぶ必要があります（`engine/src/split/src/gdn_tc_prompt.cuh:12-20,726-736`; `engine/src/split/src/kernels.cu:2008-2016`; `engine/src/split/src/engine.cu:65-66`）。これらを満たさず scan が使われない場合は通常の sub-chunk 経路に進み、診断判定の対象になります。
- HIP ビルドでは tensor-core scan のコンパイル条件を満たさないため、この scan による早期 return はありません。chunked 経路を通れば診断分岐の対象です（`engine/src/split/src/gdn_tc_prompt.cuh:12-13`; `engine/src/split/src/kernels.cu:2034-2069`）。

## 実行時の詳細

`gdn_prompt_impl` 内の `static const bool check` が、初めて chunked 経路に入った時点で環境を読み取り、その結果をプロセス内で cache します。したがって初回評価後に環境を変更しても反映されません。chunked 経路に入らない間は変数の読み取りも起きません（`engine/src/split/src/kernels.cu:2018-2037`）。

有効時は、まず device 上の GDN state を退避し、row-by-row kernel `k_gdn_pf_rec` を実行して参照出力と参照終端状態を host vector にコピーします。その後 state を退避内容に戻して stream を同期し、通常どおり `k_gdn_ch_prep` / `k_gdn_ch_rec` を実行します。chunked recurrence 後に出力と終端状態を host にコピーし、各ベクトルについて `max(abs(reference - actual)) / max(max(abs(reference)), 1e-30)` を計算します（`engine/src/split/src/kernels.cu:2037-2060`）。

比較対象の「outputs」は normalization 前の recurrence 出力 `y32` です。診断比較の後に通常の `k_gdn_pf_norm_own` が実行されます。差の閾値判定、assert、値による fallback はなく、chunked recurrence の結果をそのまま後続へ渡します（`engine/src/split/src/kernels.cu:2049-2069`）。この診断時には参照用 GPU メモリ確保、device-host 転送および stream 同期が追加されます（`engine/src/split/src/kernels.cu:2038-2047,2051-2055`）。

## ログと測定値

比較が行われるたび、stderr に次の形式で出力します。`C` はその prompt 呼び出しの行数、`outputs` と `end state` は上記の相対差です（`engine/src/split/src/kernels.cu:2061-2062`）。

```text
gdn check: C %d, outputs %.3g, end state %.3g (largest difference over largest value)
```

この変数について Strata の資料に記載された性能測定値は確認できません。ログの差が大きい場合も、この変数自身は警告・エラーを出さず、相違を理由に終了しません。

## 根拠

- prompt prefill から GDN 関数への呼び出し: `engine/src/split/src/prefill.cu:1651-1657`
- chunked 経路の既定値、入力検査、診断判定と評価順: `engine/src/split/src/kernels.cu:2018-2037`
- 参照計算・state 復元・chunked 計算・相対差ログ: `engine/src/split/src/kernels.cu:2038-2069`
- NVIDIA tensor-core scan のコンパイル・実行条件と早期 return: `engine/src/split/src/gdn_tc_prompt.cuh:12-20,726-736`; `engine/src/split/src/kernels.cu:2008-2016`
- tensor-core scan のモデル既定値: `engine/src/split/src/engine.cu:65-66`
