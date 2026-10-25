# `--no-fast-attn`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--no-fast-attn` |
| 別名 | なし |
| 値 | 取らない boolean switch |

## 役割

QSA decode の既定 split-K attention 経路を無効にし、KV を gather してから通常の QSA attention 関数を呼ぶ経路へ切り替えます。parser のコメントでは A/B（比較）用スイッチとして説明されています。性能向上を保証する設定ではありません。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --no-fast-attn
```

`--tokens` はカンマ区切りの token ID 列です。上の例は parser の usage に示された基本呼び出しへフラグを加えた形です。

## 値と既定値

- 値を取りません。指定すると `no_fast_attn = true` になります。複数回指定しても同じ boolean を true にするだけです。
- 省略時は `no_fast_attn` が `false` で、エンジンは fast attention を有効にします。
- `--no-fast-attn=true` のような値付き形式は別の引数として解釈され、未知引数エラーになります。
- このオプション専用の値 validation はありません。

## 実行時の動作

parser はフラグを `Options::no_fast_attn` に設定し、起動時に `layer_set_fast_attn(!o.no_fast_attn)` で層実装へ反映します。層実装の初期値も fast attention 有効です。QSA decode で fast attention が有効、`--native-flash-attn-short` が無効、かつ dump buffer がない場合、`qsa_decode_attn_step` を使います。このフラグを指定するとこの条件を外れ、KV 形式に応じた gather の後で `qsa_attend_step` を呼びます。

## 適用条件と副作用

- フラグの実効範囲は通常エンジン parser の `strata generate` 経路です。Qwen3.6 専用 parser は索引上別スコープであり、本調査ではその parser がこのフラグを受け付けるとは確認していません。
- `--native-flash-attn-short` が有効な場合は、フラグの有無にかかわらず split-K 経路ではなく gather 経路に入り、その後 short adapter を使います。したがってこの組み合わせでは、このフラグが attention kernel の選択に加える差はありません。
- dump buffer がある場合も fast attention 条件から外れます。この場合も同フラグによる経路差はありません。
- `layer_verify_compatible` は fast attention 無効を非互換理由「the split-K decode attention is off」とし、verify window 初期化はその理由で失敗を返します。診断エラーは `verify: ...` の形で設定されます。
- `--serve` の session config fingerprint にも `no_fast_attn` が含まれ、設定差が fingerprint に反映されます。
- この切替による速度・メモリ量の大小は、ソースだけでは一律に断定できません。測定は行っていません。

## 出力とエラー

- フラグ単独に対する専用の警告や出力はありません。
- 誤った値付き表記など未知の引数は stderr に `unknown argument: ...` を出し、usage を stderr に表示して終了コード 2 を返します。
- fast attention 無効で verify window が必要になった場合、初期化処理はエラー文字列を設定して失敗します。呼び出し側の最終終了コードはこの個別経路では追跡していません。

## 根拠

- `src/program/generate.cpp:605` — boolean の既定値と A/B 用途コメント。
- `src/program/generate.cpp:739-747` — usage の構文と基本引数。
- `src/program/generate.cpp:2781-2793` — parser での受理と未知引数時の stderr・usage・終了コード。
- `src/program/generate.cpp:3922-3933` — 起動時の設定反映および関連 `--native-flash-attn-short` 設定。
- `src/core/layer.cpp:51,537-552` — fast attention の初期値、verify 互換性判定、setter。
- `src/core/layer.cpp:1261-1292` — split-K decode 条件、gather、short adapter / 通常 attention の分岐。
- `src/core/verify.cpp:732-735` — 非互換時に verify 初期化エラーを返す処理。
- `src/program/generate.cpp:9450-9462` — session config fingerprint への格納。
- `sycl/src/program/generate.cpp:583,2061,3004`、`sycl/src/core/layer.cpp:1306-1342` — SYCL ツリーにも対応する parser・設定・attention 分岐があることを確認。上記の詳細な分岐・エラー説明は通常の `src/` 実装に基づきます。
- `CMakeLists.txt:759-762`、`sycl/CMakeLists.txt:274-276` — 通常および SYCL build で `strata` を `generate.cpp` から構成。

調査範囲はこの checkout のソースです。CLI help は実行せず、Release artifact・各 GPU/backend 上での実挙動や性能は確認していません。
