# `STRATA_DS4_PIN_GB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 エンジン `strata-dsv41` が RAM にコピーした CPU lane の expert を pin-by-need で登録するとき、登録するコピーの合計サイズの上限を GB 単位で指定します。コピーは routing profile の使用頻度をバイト数で割った順に調べ、上限を超えずに登録できたものだけを GPU が pinned copy から直接読む対象にします。上限は登録量を制限するもので、pin-by-need 自体を有効にはしません。

## 値と判定

`env_f()` は環境変数が未設定なら既定値を返し、設定されていれば `std::atof()` で変換して `float` にします。`STRATA_DS4_PIN_GB` の既定値は `0.0` です。空文字や数値として読めない文字列は `atof` により 0 となり、負数も含め `pin_cap_gb > 0` を満たさない値は上限として働きません。数値の後ろにある文字列は `atof` の変換対象外です。値の検証、丸め、範囲 clamp はありません。

| 値 | pin-by-need 経路での扱い |
|---|---|
| unset、空文字、数値でない文字列、0、負数 | 上限なし。pin 可能なコピーを登録失敗まで順に試す |
| 正数 `N` | 登録済み合計に次のチャンクを足すと `N` GB を超える場合、そこで登録を打ち切る |

サイズの換算は `1 GB = 1,000,000,000 bytes` です。判定はチャンク単位で、上限と同じサイズまでは許可しますが、チャンクを分割して上限に合わせることはありません。上限に収まらない最初のチャンクでループを終了するため、それ以降の候補も試しません。

## 有効になる条件

この変数が参照されるのは `load_experts_mx()` のコピー expert のゼロコピー pin 処理です。GGUF の expert 形式が MXFP4 であること、コピー対象があること、`--mmap-experts` によりコピー処理が抑止されていないことなどが必要です。

さらに、`zc_pin()` が実行されるには NUMA part が1つ (`NH == 1`)、RAM chunk が存在し、GGUF で `DS4_STREAM` が `atoi` で 0 にならず、`DS4_STREAM_ZC` も未設定か `atoi` で 0 にならないこと、lane に integrated GPU がないことが必要です。通常の one-GPU 経路 (`ln_one`) が無効なら、`DS4_STREAM_ZC` の設定または pin-by-need が必要で、最後に host pointer を GPU が使えるか、pin-by-need かつ単一 GPU であることも条件になります。

pin-by-need は通常 `STRATA_DS4_PIN_BY_NEED` の `atof` 結果が 0 以外のとき有効です。ただし Windows CUDA では `ln_one` が有効で、この変数が未設定または空文字なら pin-by-need が既定で有効です。明示した `STRATA_DS4_PIN_BY_NEED=0` はその既定を無効にします。pin-by-need が無効で `DS4_STREAM_ZC` により通常の pin 経路に入る場合は全 chunk の登録を並列に試す分岐となり、`STRATA_DS4_PIN_GB` は適用されません。また、先行する `DS4_COPY_PIN` ですでにコピーが pin されている場合も上限判定を通らず、その pin をそのまま使います。

## 実行時の詳細

上限値は `ds4_model.cu` 内の `env_f` によってエンジンオブジェクトのメンバー初期化時に読み取られます。読み取り結果はそのインスタンスの `pin_cap_gb` に保持され、`zc_pin()` 内で pin-by-need 分岐に入ったときに使われます。要求や decode ごとに読むコードではありません。

pin-by-need では各 RAM chunk の routing profile hit 数を集計し、chunk サイズあたりの値が大きい順に安定ソートします。各 chunk の登録には `cudaHostRegister(..., cudaHostRegisterPortable | cudaHostRegisterMapped)` を使います。上限を超える場合は次の登録前に終了し、登録 API が失敗した場合もエラーを消去して同様に終了します。残りの expert は staging 経由になります。登録した chunk の mapped pointer 取得に失敗した場合、その chunk は unregister されて直接読み込み対象から外れます。

pin-by-need の処理完了時には stderr に `ds4: PCIe lane: pin by need: ... of the copies' ... GB pinned, the most-used layers first ...: those pulled in place, the rest through the staging` 形式の行が出ます。上限到達自体の専用警告やエラー終了はありません。登録失敗のときも pin-by-need ループは残りの登録を止め、最終的な pinned 容量を同じログで報告します。

## 根拠

- `src/dsv41/ds4_model.cu:1352-1355` — `env_f` の既定値処理と `atof` → `float` 変換。
- `src/dsv41/ds4_model.cu:5760-5768,5842-5844,5881-5890,6290-6292` — MXFP4 expert のロード経路、コピー条件、コピー budget がない場合の早期 return。
- `src/dsv41/ds4_model.cu:6053-6068` — pin-by-need の説明、Windows CUDA の既定、および上限値の読み取り。
- `src/dsv41/ds4_model.cu:6176-6186` — zero-copy pin の条件。
- `src/dsv41/ds4_model.cu:6199-6244` — 使用頻度順、チャンクごとの上限判定、pin 登録と失敗処理。
- `src/dsv41/ds4_model.cu:6245-6278` — mapped pointer の扱い、登録量の集計、stderr ログ。
- `docs/DETAILS.md:275-279` は別経路の `STRATA_PIN_BY_NEED` / `STRATA_ARENA_PIN_GIB` を説明しており、DS4 の `STRATA_DS4_PIN_GB` の説明根拠にはしていません。
