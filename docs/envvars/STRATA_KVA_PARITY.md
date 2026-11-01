# `STRATA_KVA_PARITY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 所有ソースを対象とし、外部ライブラリの挙動は含めない。

## 役割

現 commit では、この変数は KVA 設定の `parity` フラグに読み込まれます。フィールド宣言のコメントには「state-only path を full path と比較して報告する」とありますが、本番ソース内でこのフィールドを参照する箇所はなく、比較・報告を実行する処理も確認できません。したがって、現在のコードから実際の機能や出力を確認できない、読み取り後に使われない設定値です。

## 値と判定

共通 helper `kva_env_flag()` が値を数値変換せず、先頭文字だけで判定します。未設定または空文字なら既定値 `false`、それ以外は先頭文字が `'0'` なら `false`、そうでなければ `true` です。

| 値 | `KvaConfig::parity` |
|---|---|
| 未設定 | `false` |
| 空文字 | `false` |
| `0`, `0anything` | `false` |
| `1`, `true`, `false`, `anything` | `true` |

大文字小文字、空白、文字列全体の妥当性は検査しません。たとえば `false` は先頭文字が `f` のため `true` になります。この判定結果は設定構造体に格納されますが、現 commit の本番処理では使われません。根拠: `include/strata/prefill/kva.hpp:82,143-146,160`。

## 有効になる条件

値が `true` でも、現 commit ではそれによって有効になる比較処理はありません。KVA の主スイッチ `STRATA_KVA`、GPU backend、モデル形状、prompt 条件、CLI オプションによって `parity` の効果が変わる処理も見つかりませんでした。

KVA 設定自体は engine 起動経路で取得され、設定後に prefill の KVA 判定・ログが行われます（`src/program/generate.cpp:6263-6278`, `src/prefill/prefill.cpp:2947-2965,5820-5831`）。しかし、これらの処理が参照するのは KVA の有効状態、mode、layer 選択などであり、`parity` は参照されません。

## 実行時の詳細

`kva_config_from_env()` は `STRATA_KVA_PARITY` を `kva_env_flag()` に渡して `KvaConfig::parity` に格納します。通常の engine 経路では `kva_config()` の関数内 static な設定値として初回に作られ、そのプロセス内で再利用されます。したがって、engine がこの設定を初期化した後に環境を変更しても、通常経路のキャッシュ済み設定には反映されません（`include/strata/prefill/kva.hpp:149-160,191-195`）。

リポジトリ内で候補名を完全一致検索すると、本番コードの読み取りは上記一箇所です。その他の参照は設定フィールドのコメントと `src/prefill/kva_test.cpp:32` のテスト用環境変数クリア一覧です。本番コードに `KvaConfig::parity` の読み取りはなく、`STRATA_KVA_PARITY` を理由とするログ、警告、終了、失敗経路もありません。コメントが記す parity 報告と現行実装との食い違いとして記録します。

## 根拠

- `include/strata/prefill/kva.hpp:82` — `parity` フィールドの宣言とコメント。
- `include/strata/prefill/kva.hpp:143-146,160` — 値の判定 helper と環境からの代入。
- `include/strata/prefill/kva.hpp:149-160,191-195` — 設定構築とプロセス内 static cache。
- `src/program/generate.cpp:6263-6278` — engine 起動経路での設定取得と KVA の process-wide 条件処理。
- `src/prefill/prefill.cpp:2947-2965,5820-5831` — prefill の KVA 判定とログ。parity フィールドは参照しない。
- `src/prefill/kva_test.cpp:32` — テスト用環境クリア一覧に名前がある（本番機能の根拠ではない）。
