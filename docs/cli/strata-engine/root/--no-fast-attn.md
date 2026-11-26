# `strata --no-fast-attn`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root） |
| オプション | `--no-fast-attn` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

QSA attention の decode で、既定の split-K 経路を無効にし、KV を gather して one-block-per-head の attention 経路を使わせます。CUDA と SYCL の `generate` parser の両方で受理され、各実装が同じ `layer_set_fast_attn` 設定を行います。これは `strata-engine` の root オプションであり、Terminal CLI の `strata` とは別です。

## 使い方

```sh
# 通常の engine generate 引数に追加して、split-K decode attention を無効にする
strata --pack ./pack --tokens "1,2,3" --no-fast-attn
```

## 値と既定値

値は取りません。CUDA parser の `Options::no_fast_attn` は `false` で初期化され、SYCL parser にも同じ初期値があります。そのため未指定時は `layer_set_fast_attn(true)` となり、高速経路が有効です。指定すると真になり、呼び出し時に高速経路を無効にします。同じフラグを複数回指定しても真を再設定するだけです。値検証やオプション固有の範囲検査はありません。parser は `--no-fast-attn` を値を読む分岐として扱わないため、値を続けて書く形式はこのオプションの構文ではありません。

## 実行時の動作

CUDA parser は `o.no_fast_attn` を設定し、初期化時に `layer_set_fast_attn(!o.no_fast_attn)` へ渡します。SYCL parser にも同じ処理があります。各 core 実装では `g_fast_attn` が既定 `true` で、この setter が値を更新します。

QSA layer の decode は、`g_fast_attn` が有効で、`native_flash_attn_short` が無効、かつ dump 用バッファがない場合に split-K の `qsa_decode_attn_step` を呼びます。それ以外は KV gather を行い、短縮 flash attention が有効ならその adapter、そうでなければ `qsa_attend_step` を使います。したがって本フラグ指定時は gather 側になりますが、`--native-flash-attn-short` や dump による別経路の条件も同じ分岐に作用します。

serve 用の session config fingerprint にも `no_fast_attn` が switch として含まれます。ソース上、この設定は layer 設定として起動時に渡されており、リクエスト単位で切り替える CLI 処理は確認できません。

## 適用条件と副作用

効果が確認できるのは `engine/src/core/layer.cpp` と `engine/sycl/src/core/layer.cpp` の QSA layer decode 分岐です。`layer_verify_compatible` は `g_fast_attn` が無効な場合に split-K decode attention が無効である理由を返し、verify 互換条件を満たさない扱いにします。

このフラグ固有のファイル・ネットワーク操作や追加の警告は確認できません。attention 実装経路を変え、serve の session config fingerprint にも設定差が反映されます。速度や精度の定量的な影響は、このソース調査では測定していません。

## 出力とエラー

このフラグ自体に成功メッセージや専用エラー経路はありません。未知の引数は `unknown argument: ...` を stderr に出し、usage を表示して parser が終了コード `2` を返します。値を別トークンで後置した場合のその値の扱いをこのオプション専用に定める処理はなく、後続トークンは通常の引数解析に回ります。

## 根拠

- `engine/src/program/generate.cpp:956,4264` — CUDA parser の既定値とフラグ受理。
- `engine/sycl/src/program/generate.cpp:622,2210` — SYCL parser の既定値とフラグ受理。
- `engine/src/program/generate.cpp:6108`、`engine/sycl/src/program/generate.cpp:3223` — parser 値を反転して layer 設定へ渡す。
- `engine/src/core/layer.cpp:51,551,1287-1313` — CUDA 側の既定値、setter、split-K と gather/attention の分岐。
- `engine/sycl/src/core/layer.cpp:47,553,1309-1328` — SYCL 側の同等の既定値、setter、分岐。
- `engine/src/core/layer.cpp:537-546` — verify 互換条件で高速 attention 無効を拒否理由にする。
- `engine/src/program/generate.cpp:14017-14029` — serve session config fingerprint に switch を含める。
- `engine/src/program/generate.cpp:4268-4273` — 未知引数の stderr、usage 表示、終了コード `2`。
