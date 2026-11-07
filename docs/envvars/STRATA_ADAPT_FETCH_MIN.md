# `STRATA_ADAPT_FETCH_MIN`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_ADAPT_FETCH` による PCIe share から VRAM cache への expert admission で、候補 expert の最低 routing usage を指定します。対象候補の usage がこの値以上の場合にだけ、admission 候補として次の比較へ進みます。既定値は `1.0` です。

この変数単独では機能を有効にしません。`STRATA_ADAPT_FETCH` が有効で、適応 tier、residency table、GPU plan、PCIe share などの条件を満たしたときだけ読み取られ、使用されます。

## 値と判定

値は `std::atof` で `float` に変換され、値域の検査や clamp はありません。未設定なら `ExpertDispatch` の初期値 `1.0f` が残ります。空文字は設定済みとして変換され `0.0` になります。数値として読める先頭部分を変換し、変換できない文字列は `atof` の結果 `0.0` になります。したがって、例えば `2.5tail` は `2.5`、`invalid` は `0` として扱われます。

| 環境変数の状態 | `fetch_min` |
| --- | ---: |
| 未設定 | `1.0`（既定値） |
| `2`, `2.5tail` | `2.0`, `2.5` |
| 空文字、数値変換できない文字列 | `0.0` |
| 負数 | 負数のまま |

候補の選別では `usage[e] >= fetch_min` が条件です。負数や `0` は最低使用回数の足切りを下げますが、実際に admit されるには、別途 `STRATA_ADAPT_FETCH_MARGIN` による resident victim との比較も必要です。NaN の比較は成立しません。既定の `fetch_margin` は `0.5` で、candidate の usage が victim の usage より少なくとも margin 分大きくなければ admission されません。

## 有効になる条件

この値が読み取られるのは `STRATA_ADAPT_FETCH` が正のときだけです。同変数は `generate.cpp` 内で最初の呼び出し時に一度だけ読み、未設定は無効、設定値は `atoi` で整数化して 0〜2 に clamp します。よって `STRATA_ADAPT_FETCH_MIN` に CLI 上の直接指定や優先順位はなく、CLI の `--adapt-every` と `--adapt-swaps` は適応 tier の有無に関係しますが、MIN 値を上書きしません。

さらに、admission の実行には次が必要です。

- 適応 tier が有効で、usage table が空でないこと（通常は `--adapt-every` と `--adapt-swaps` が正であること）。
- residency table と GPU plan があり、PCIe share が正であること。
- PCIe plan が kernel copy mode（内部値 `2`）で、対象 layer が PCIe fetch 可能であること。
- layer split、peer tier、helper GPU、Foresight、resident RAM mode など、各呼び出し元が拒否する条件に該当しないこと。
- 対象 layer の PCIe share が実際に expert miss を fetch すること。候補は未 resident、pinned、window で tail-skip されず、adaptive tier の in-flight copy 中でない必要があります。

`strata serve` は加えて `--spec-split`、`--adapt-async`、`--pipeline-windows`、`--batch`、`STRATA_ADAPT_OVERLAP=1`、`--pcie-mode dma/direct` の場合などに feature を停止します。`strata generate` も `--spec-split`、分割/peer/helper GPU、`--pcie-mode dma/direct`、resident RAM mode を停止理由にします。停止時は `STRATA_ADAPT_FETCH is off (...)` を stderr に出し、MIN 値の読み取り・閾値ログ出力はしません。

## 実行時の詳細

`strata serve` の初期化時と `strata generate` の実行初期化時に、上記の feature 条件を通った場合だけ環境から値を読み、`drive.d.fetch_min` に保存します。以降の各 window では、layer の miss のうち usage が高い順に PCIe share で fetch する候補を選び、その fetched candidate の usage が `fetch_min` 以上なら victim との margin 比較に進めます。比較相手はその window で route されていない resident expert のうち usage が低いものです。条件成立時は fetched blob を victim の VRAM slot にコピーし、residency table を更新します。これは PCIe fetch 済み blob を cache slot に admit する処理です。

閾値は各 serve/generate 初期化で保存され、その実行中に環境値を変更しても再読込されません。設定値が有効な構成では stderr に `strata serve: STRATA_ADAPT_FETCH=...` または `strata generate: STRATA_ADAPT_FETCH=...` とともに、採用された minimum と margin が小数2桁で表示されます。generate は終了時に fetch admission の合計と1 round あたりの件数も表示します。`STRATA_ADAPT_FETCH_VERIFY` が設定されていれば、generate は admission 済み slot を読み戻して不一致を stderr に出しますが、この検証環境変数は MIN の判定には関与しません。

MIN の無効文字列について専用の警告・エラー・終了経路はなく、`atof` の変換結果がそのまま使われます。admission 後のコピーや verifier の失敗処理は通常の dispatch 経路に属し、MIN 自体による fallback はありません。

`docs/DETAILS.md:1076` は適用条件に `STRATA_ADAPT_OVERLAP=1` を挙げています。現行ソースでは serve 側が overlap 有効時に fetch を止める一方、generate 側の停止条件と `ExpertDispatch::fetch_can()` には overlap 判定がありません。この条件差はソースにある実装差として扱い、共通条件とはしません。

## 根拠

- `include/strata/core/expert_source.hpp:658-675`: `fetch_min` の既定値 `1.0f`、その用途、関連 state。
- `src/program/generate.cpp:2005-2010`: `STRATA_ADAPT_FETCH` の読み取り、既定・clamp。
- `src/program/generate.cpp:12772-12795`: serve の有効条件、MIN 読み取り、採用閾値のログ。
- `src/program/generate.cpp:20441-20473`: generate の PCIe mode / share 設定、適用条件、MIN 読み取り、ログ。
- `src/core/expert_source.cpp:4734-4737`: pool 側の fetch 可否条件。
- `src/core/expert_source.cpp:5013-5029,5055-5065`: PCIe fetch 候補と routing usage 順の選択。
- `src/core/expert_source.cpp:5095-5136`: 最低 usage 判定、victim margin 比較、slot/residency 更新。
- `src/program/generate.cpp:20976-20995,21183-21188`: generate の任意 slot read-back 検証と admission 集計出力。
- `docs/DETAILS.md:1076`: 説明資料に記載された feature 条件と測定概要。条件の差分は上記の現行ソースを根拠とした。
