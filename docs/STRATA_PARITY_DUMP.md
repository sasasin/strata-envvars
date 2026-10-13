# `STRATA_PARITY_DUMP`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_PARITY_DUMP` は、`route_resident_parity` CUDA テストが参照実装と本番用 resident-route kernel の比較で不一致を検出した場合に、入力と両者の出力の詳細を標準出力へ追加する診断用スイッチです。参照実装、本番用 kernel、比較条件を切り替える変数ではありません。

この読み取りはテスト用ソース `src/kernels/route_resident_parity.cu` にだけあります。CMake は同ファイルから `route_resident_parity` 実行ファイルと CTest を登録します。したがって、この変数の効果は当該テストを実行した場合に限られ、通常の Strata エンジンの実行動作を制御する根拠はありません。

## 値と判定

値の内容は parse されません。`std::getenv("STRATA_PARITY_DUMP")` の結果が null でないかだけを判定します。

| 状態 | 詳細ダンプ |
|---|---|
| 未設定 | しない |
| 空文字を含む、何らかの値が設定済み | する |

`0`、`false` を含め、どの文字列でも設定されていれば有効です。大文字小文字や数値としての妥当性は見ません。判定は起動時にキャッシュされず、不一致処理に入ったときに評価されます。

## 有効になる条件

- `route_resident_parity` の実行中であること。このターゲットは CUDA ソースとして CMake に登録され、resident-route の warp 版と scalar 参照実装を合成データで比較するテストです。
- 比較結果に不一致があること。対象は expert ID、重み、4つの統計カウンターのいずれかです。一致したケースでは環境変数を設定しても詳細ダンプは出ません。
- その実行でダンプした不一致ケースがまだ2件未満であること。上限に達すると後続の不一致は詳細表示されません。

## 実行時の詳細

テストは不一致ごとにケース番号、token 数、margin、rank 範囲、tie-heavy フラグ、ID・重み・統計の一致状況を `printf` で表示します。この要約表示は `STRATA_PARITY_DUMP` の設定に関係なく行われます。不一致があり、変数が設定済みで、まだ2ケースを出力していなければ、各 token について入力 ID、参照側 ID、並列 kernel 側 ID、参照側 ID に対応する logits、および両側の重みのビット表現を追加表示します。これらは標準出力への出力です。

テスト本体では固定 seed `20261010u` から生成した240ケースを CUDA 上で比較し、モデルは読み込みません。失敗時の最終サマリーと終了コードはこの変数に左右されません。

## 根拠

- `src/kernels/route_resident_parity.cu:138-140,195-218`: `dumped` の初期値、ケース比較、不一致時のみの `getenv` 判定と2ケース上限。
- `src/kernels/route_resident_parity.cu:220-237`: 詳細として表示する ID、logits、重みの内容。
- `src/kernels/route_resident_parity.cu:243-254`: テスト全体のサマリーと終了コード。
- `CMakeLists.txt:99,902-908`: テストビルド設定と `route_resident_parity` 実行ファイル／CTest の登録。登録コメントは GPU・合成データ・モデルなしと明記。
- `docs/DETAILS.md:1638-1640`: `STRATA_ROUTE_RESIDENT` などの説明はあるものの、`STRATA_PARITY_DUMP` の記載はありません。実装箇所はテストソースだけであり、通常のエンジン設定としての意味は確認できません。
