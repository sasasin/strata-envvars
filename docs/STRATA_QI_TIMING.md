# `STRATA_QI_TIMING`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。Strata 所有のソースを対象とし、外部ライブラリの環境変数動作は対象外。

## 役割

Qwen-Image-2.1 用の Strata native DiT runner が正常に計算を完了したとき、1回の `compute()` の経過時間、画像 token 数、テキスト prefix token 数を `LOG_INFO` に出します。計算方法や実行経路を切り替える変数ではなく、計測ログの出力だけを制御します。

## 値と判定

| 環境変数の状態 | `timing` | 動作 |
|---|---:|---|
| 未設定 | `false` | step timing の `LOG_INFO` を出さない |
| 空文字を含む、何らかの値が設定済み | `true` | 成功した native `compute()` ごとに step timing を出す |

値の内容は parse も比較もしません。`getenv("STRATA_QI_TIMING") != nullptr` の判定なので、`1` に限らず `0`、`false`、空文字も有効です（`tools/image/sdcpp_native/qwen_image_2_1_native.hpp:80-89`）。値は runner のコンストラクターで `timing` メンバーに一度保存されます。runner 作成後に環境を変更しても、その runner には反映されません。

## 有効になる条件

この変数が参照されるのは native runner が作成された場合だけです。Strata の適用スクリプトは CUDA または HIP build のときだけ native runner を組み込み、`qwen_image_2_1_native=1` が model args にあり、DiT model path が空でない場合にその runner を選びます。画像 endpoint からは設定の `native` が有効な場合に同じ model arg を追加します（`tools/image/sdcpp_native/apply.py:1-10,27-51`; `serve/images.py:127`）。

runner 作成後も、入力 shape が想定外、reference image を含む、fused MLP でない、backend が CUDA/HIP でないなどの条件では stock runner に fallback し、native step timing は出ません。レイアウトが未対応の画像 prompt や、重み・activation 割り当て・kernel 等の失敗で fallback する経路も同様です（`tools/image/sdcpp_native/qwen_image_2_1_native.hpp:445-493,524-527,553-555,571-574`）。

## 実行時の詳細

native `compute()` の入力チェックを通過した後、`steady_clock` の開始時刻を取得します。そこから重みの初回 GPU load、activation 確保、native 計算、backend 同期、出力 tensor の取得と host 側の並べ替えまでを含みます。終了時に `timing` が true なら、次の形式で `LOG_INFO` を呼びます。

```text
Qwen Image 2.1 native: step %.1f ms (%lld image tokens, prefix %lld)
```

時間はミリ秒、小数点以下1桁です。token 数は `T = Wd * Hd` と入力 context の長さ `Lt` です。ログは成功した native `compute()` 呼び出し単位で出るため、初回呼び出しでは重みの初回 load 時間も含みます。stock runner に fallback して戻る経路や、native 計算が失敗した経路はこのログ箇所に到達しません（`tools/image/sdcpp_native/qwen_image_2_1_native.hpp:468-480,583-595`）。

## 根拠

- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:80-89` — constructor での環境読み取りと bool 保存。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:445-493` — 対象の native `compute()` と fallback 条件、時間計測開始。
- `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:583-595` — 同期・結果取得後の timing ログと token 数。
- `tools/image/sdcpp_native/apply.py:1-10,27-51` — native runner の適用条件と CUDA/HIP build 条件。
- `serve/images.py:127` — image endpoint が native 設定時に model arg を追加。

`docs/DETAILS.md` および `tools/image` の資料を検索した範囲では、この timing 出力の仕様や測定値を説明する記載は見つかりませんでした。ここではソース上のログ動作のみを記録しています。
