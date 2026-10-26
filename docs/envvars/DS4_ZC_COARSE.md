# `DS4_ZC_COARSE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek-V4.1 エンジンの RAM expert store を GPU から直接読めるよう登録する際、HIP ビルドでは `cudaHostRegister` に渡す登録フラグへ `0x8u` を追加します。コードコメントはこれを coarse-grained 登録の test arm と呼んでいます。環境変数自身は登録フラグを変えるだけで、store の利用や GPU mapping を単独で有効にはしません。

## 値と判定

`DS4_ZC_COARSE` は文字列比較ではなく `std::atoi` で整数へ変換し、変換結果が 0 以外なら有効です。値全体の形式検証や範囲制限はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効。追加フラグなし |
| 空文字、数字で始まらない文字列、`0`、`0suffix` | `atoi` が 0 を返すため無効 |
| `1`、`2suffix`、負の非ゼロ整数 | `atoi` が非ゼロを返すため有効 |

空白や符号などの解釈は `atoi` の変換規則に従います。コードは値をキャッシュせず、RAM store の各 arena chunk を GPU に登録する callback 内で環境を読み直します。

## 有効になる条件

- `strata-dsv41` がビルドされている必要があります。CMake では `STRATA_BUILD_DSV41` は既定 OFF で、DSV41 ターゲットは CUDA または HIP バックエンドのブロック内にあります。
- `DS4_ZC_COARSE` の判定コードは `#if defined(STRATA_USE_HIP)` の内側にあります。したがって HIP ビルドでのみ追加フラグが適用され、CUDA ビルドではこの変数はこのコード経路に影響しません。gfx906 専用ビルドは DSV41 ターゲット条件から除外されています。
- RAM store 初期化には、store サイズが正、expert layer が存在し、先頭 layer の形式が MXFP4、file experts があることが必要です。
- GPU mapping はさらに `DS4_STORE_ZC` が設定され `atoi` の結果が非ゼロであり、GPU が1台、先頭 layer の model count が1の場合に要求されます。これらを満たさない場合、`DS4_ZC_COARSE` 単独では何も起きません。

## 実行時の詳細

`init_store()` が上の条件を満たすと `cfg.map_chunk` を設定します。arena の chunk ごとに `ExpertStore::grow()` がこの callback を呼び、HIP では通常の `cudaHostRegisterMapped | cudaHostRegisterPortable` に加えて、`DS4_ZC_COARSE` が非ゼロなら `0x8u` を OR して `cudaHostRegister(h, n, reg_flags)` に渡します。変数の読み取りは chunk 登録時なので、初回の store 初期化後に増える chunk でも、その時点の環境値が参照されます。

登録に失敗すると callback は `nullptr` を返します。device pointer の取得に失敗した場合は、その chunk の host registration を解除してから `nullptr` を返します。chunk の GPU mapping が成立しなければ、store 自体の初期化を直ちに失敗させるのではなく、`init_store()` が `ds4: RAM store: the arena could not be mapped for the GPU: zero-copy off` を stderr に出して zero-copy 用の layer 状態を消します。

## 根拠

- `src/dsv41/ds4_model.cu:4633-4635` — RAM store 初期化の早期 return 条件。
- `src/dsv41/ds4_model.cu:4668-4706` — `DS4_STORE_ZC` の条件、HIP 限定の `DS4_ZC_COARSE` 読み取り、登録 flag と失敗時処理。
- `src/dsv41/ds4_model.cu:4710-4745` — store 初期化後の mapping 確認と zero-copy 無効化ログ。
- `src/dsv41/ds4_store.hpp:480-493` — chunk を commit した後に `map_chunk` を呼ぶ処理。
- `CMakeLists.txt:797-811` — DSV41 のビルド option とターゲット条件。`STRATA_BUILD_DSV41` は既定 OFF。
- `docs/DETAILS.md` と関連するエンジン文書には `DS4_ZC_COARSE` の説明は見つからず、値域や効果の追加根拠となる測定記録も確認できませんでした。
