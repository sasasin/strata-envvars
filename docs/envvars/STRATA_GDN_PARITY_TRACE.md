# `STRATA_GDN_PARITY_TRACE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

GDN parity harness `gdn_parity` が q8_1 destination の検査を始めるとき、対象ケースを示す trace 行を stdout に出すかを制御します。検査や GDN kernel の選択・結果には影響しません。engine、server、通常の CLI 実行経路で読む箇所は見つかりませんでした。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | trace 行を出さない |
| 空文字を設定 | trace 行を出す（`getenv()` が null でないため） |
| 任意の非空文字列 | trace 行を出す。値の内容や数値変換は行わない |

`1` との比較や真偽値の parse はありません。CLI 引数や別の環境変数による上書きもありません。根拠: `src/kernels/gdn_parity.cpp:512-514`。

## 有効になる条件

`gdn_parity` が実行され、q8_1 destination の比較に進むケースでのみ参照されます。そのケースの判定条件は `c.tb < n` です。CMake では GPU runtime と `strata_kernels` にリンクした `gdn_parity` 実行ファイルを定義し、`gdn_parity --selftest` と `STRATA_GDN_SPLIT=1` を設定した同じ harness のテストを登録しています（`CMakeLists.txt:1389-1396`）。この変数自体は build macro、OS、モデル状態を調べず、通常のモデル推論を有効化する設定でもありません。

## 実行時の詳細

値は q8_1 検査ループの各該当ケースで `std::getenv()` により直接確認され、static cache されません。設定されていると `trace: T=<T> '<case>' with a q8_1 destination` を stdout に出してから、multi-token GDN の q8_1 destination と `native_quantize_q8_1` の出力・未書き込み領域を比較します。未設定でも比較は同じように実行され、抑制されるのはこの案内行だけです（`src/kernels/gdn_parity.cpp:512-540`）。

不一致時は別の `*** gdn_step_norm_multi ...` 行を stdout に出して失敗数に加算し、最後に `gdn: <件数> failures` を出して終了コード 1 を返します。環境変数の値によってこの失敗判定は変わりません（`src/kernels/gdn_parity.cpp:535-547,622-625`）。

## 根拠

- リポジトリ全体で候補名を検索した結果、実参照は `src/kernels/gdn_parity.cpp:513` の 1 箇所です。環境読み取り helper や動的な名前渡し経由の参照もありません。
- 候補一覧 `docs/envvars/000_envvers.md:829` には名前がありますが、用途はアプリ設定ではなく parity harness の診断出力です。
- `docs/DETAILS.md` および関連設計資料から、この変数について追加の動作仕様は確認できませんでした。
