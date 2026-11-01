# `STRATA_PREFILL_COPY_EVENT_EVERY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

chunk-major prefill の streamed expert copy で、copy 完了を示す CUDA event を何 entry ごとに記録するかを指定します。既定値は `1` で、各 expert copy の後に event を記録します。`2` 以上にすると event を間引き、compute stream は必要な entry 以降で最初に記録された event を待ちます。copy stream の順序により、その event が先行 entry のコピーもカバーします。

この値はコピーする expert やデータを変更する設定ではなく、記録・待機する event の粒度を変える tester switch です。実際に疎な event 記録になるのは、長い chunk の streamed walk と threaded issuer の両方が有効な場合です。

## 値と判定

`src/prefill/prefill.cpp` は環境値を `std::atoi` に渡し、`copy_event_every_from()` が結果を `1..64` に制限します。文字列全体の妥当性検証はありません。`atoi` が先頭の空白と符号を許し、数字列以降を無視するため、たとえば `"  +3tail"` は `3`、`"junk"` は `0` として扱われます。

| 環境値 | 結果 |
|---|---:|
| 未設定 | `1` |
| 空文字 | `1`（`atoi("")` は `0`） |
| 数値として `1` 以下 | `1`（`0`、負数を含む） |
| `2..63` | その整数 |
| `64` 以上 | `64` |
| 数字で始まらない文字列 | `1`（`atoi` の結果 `0`） |

小数は整数部分の数字列までしか読まず、数値の後ろに続く文字も検査しません。`atoi` の整数型範囲を超える入力については、実装に安全な範囲検証がありません。

値の判定結果は `run_impl()` 内の function-local `static const int` に保存されます。最初にその宣言へ到達した時点で一度だけ読み取り、同じプロセスで後から環境値を変えても再評価されません。CLI 引数や設定ファイルからこの値を上書きする経路はありません。

## 有効になる条件

疎な event 記録は、次のすべてを満たすときだけ有効です。

- 通常の chunk-major `run_impl()` 経路に入る。layer-major prefill が選択されて準備に成功した場合は `run_layer_major()` が使われ、この設定箇所を通りません。
- `stream_all` が真である。これは `m.ring > STAGE`（`STAGE` は 8）、`T >= stream_all_min()`、`m.src != nullptr` のときです。
- `STRATA_PREFILL_ISSUER` が有効で、threaded issuer が使われる。これは未設定なら既定で有効、設定時は `atoi(value) != 0` です。`STRATA_PREFILL_ISSUER=0` などで issuer が無効なら、この変数を `2` 以上にしても各 entry の event 記録・従来の wait のままです。
- この変数の判定値が `2` 以上である。

`strata_prefill` は CUDA/HIP runtime とリンクされる共通 prefill ライブラリです（`CMakeLists.txt:819-825`）。Metal の `Prefill::run()` は `metal_engine::prompt_run()` へ直接委譲して戻るため、この CUDA event の処理は適用されません（`src/prefill/prefill.cpp:7222-7231`）。

## 実行時の詳細

threaded issuer が動き、判定値が `2` 以上なら `sparse_copied` が真になります。issuer は copy stream 上で entry を順番に転送し、N 個ごとと最後の entry に event を記録します。また、stager 待ちで issuer が止まる前にも、それまで発行済みの範囲を覆う event を記録します。compute 側は必要な entry 以降で最初に記録済みの event を選び、その event を待ちます。MMQ group gather を使う経路では group の最後の streamed copy に対応する event を待ちます（`src/prefill/prefill.cpp:3511-3519,3555-3556,3571-3585,5190-5195`）。

threaded issuer が動いていて、疎な event 記録または `STRATA_PREFILL_COPY_WAIT_DEDUPE` が有効な場合、プロセス内で一度 stderr に次の形式のログを出します。後半は同じ wait-dedupe 変数の状態を表示します。

```text
strata: prompt copies: a copied event every N streamed experts (STRATA_PREFILL_COPY_EVENT_EVERY), a wait per slot (STRATA_PREFILL_COPY_WAIT_DEDUPE)
```

wait-dedupe も有効なら末尾は `one wait per release event` になります。値が `1` で wait-dedupe も無効なら、このログは出ません（`src/prefill/prefill.cpp:3486-3498`）。

この環境変数自体に不正値警告や即時終了の経路はありません。copy/event 操作のエラーはこの箇所で個別に検査されず、後続の stream 同期でエラーが表面化した場合、`run_impl()` は compute stream について `prefill: ...`、copy stream について `prefill: expert copy stream: ...` を `err` に設定して失敗を返します。呼び出し元の `Prefill::run()` は失敗を返します（`src/prefill/prefill.cpp:5762-5769,7271-7280`）。この失敗経路は event 間引きの値に固有のものではありません。

## 根拠

- 候補一覧には名前がありますが、直接の環境読み取りは `src/prefill/prefill.cpp:3482-3485` の `std::getenv` です。リポジトリ全体での完全一致検索では、同ファイルのコメント・ログ参照と `include/strata/prefill/copy_events.hpp` のコメント／helper 以外に読み取り箇所はありません。
- 変換後の clamp: `include/strata/prefill/copy_events.hpp:15-16`。
- streamed walk の条件、issuer の既定値と値判定: `src/prefill/prefill.cpp:3332,3459-3473`。
- event の間引き・consumer wait: `src/prefill/prefill.cpp:3511-3519,3555-3585`。
- layer-major 経路と Metal 経路: `src/prefill/prefill.cpp:7222-7271`。
- 基準文書 `docs/DETAILS.md` に本変数の具体的な挙動説明は見つかりませんでした。外部ライブラリや driver が同名の値を読む挙動については記載していません。
