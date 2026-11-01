# `DS4_LANE_SPIN_MS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 の decode 経路にある CPU lane サービススレッドが、次の routing request を待つ間に spin する時間をミリ秒で指定します。値は CPU lane の専門家計算や選択結果を変える設定ではなく、request がまだ届かない間に短い sleep へ移るまでの待ち時間です。

## 値と判定

`serve_lane()` 内で `std::getenv("DS4_LANE_SPIN_MS")` が null なら既定値 `250` を使い、設定されていれば `std::atol()` の結果を使います。変換後に範囲検査、clamp、エラー処理はありません。

| 環境変数の状態 | `spin_ms` |
|---|---:|
| 未設定 | 250 ms |
| 空文字 | 0 ms（`atol("")`）|
| 整数変換可能な文字列 | `atol` が読み取る符号付き整数値。先頭空白と符号を受け付け、数字以降の文字列は検査しない（例: `12ms` は 12）|
| 数字として変換できない文字列 | 0 ms |
| 負数 | 負のミリ秒値。無効値として拒否も clamp もされない|

`atol` を使うため、浮動小数点値としては解釈されません。整数として表現できない大きさの入力に対する結果はこのコードで検査・規定していません。

## 有効になる条件

この変数の読み取り箇所は `src/dsv41/ds4_model.cu` の `serve_lane()` だけです。CMake では DeepSeek-V4.1 エンジンの `strata-dsv41` ターゲットを `STRATA_BUILD_DSV41` で追加し、このオプションは既定で OFF です。したがって、そのターゲットを含むビルドで同エンジンの decode lane が動作する場合に適用されます（`CMakeLists.txt:906-920`）。

`Impl` の初期化で request/response ring を準備した後、lane 用サービススレッドが起動し、そのスレッドから `serve_lane()` が呼ばれます（`src/dsv41/ds4_model.cu:3131-3156`）。この設定に追加の CLI 引数や別の環境変数による上書きはありません。

## 実行時の詳細

変数は `serve_lane()` の request 不在分岐で `static const long` として初めて実行されるときに読み取られ、以後プロセス内で同じ値が使われます。request が ring slot に届いていない間、lane は `cpu_relax()` を行い、最後に answer を公開してからの経過時間が `spin_ms` を超えた後は、繰り返しの待ちに短い sleep を挟みます。answer の公開後に基準時刻 `last` が更新されます（`src/dsv41/ds4_model.cu:7454-7482,7632-7635`）。

負数や 0 では経過時間が閾値を超えやすく、通常は空き待ちのたびに sleep 分岐へ進みます。正数では、最後の answer の後その時間が過ぎてから sleep 分岐へ進みます。ログ、警告、終了・失敗経路はこの設定値に対して実装されていません。

Windows では、sleep 分岐で別変数 `DS4_LANE_NAP` が文字列全体で `sleep` と一致しなければ高分解能 waitable timer を試し、timer が得られない場合は `sleep_for(20 µs)` に進みます。`DS4_LANE_NAP=sleep` の場合も `sleep_for(20 µs)` に進みます。Windows 以外はこの条件付き timer 部分を通らず `sleep_for(20 µs)` を使います（`src/dsv41/ds4_model.cu:7468-7481`）。これは spin 時間とは別の待機方式の選択です。

## 根拠

- 候補名の全参照: `src/dsv41/ds4_model.cu:7466-7468`。7466 行は設定の説明コメント、7467 行が環境からの唯一の読み取りです。
- lane の待機条件と Windows の sleep 方式: `src/dsv41/ds4_model.cu:7461-7482`。
- answer 公開と待機基準時刻の更新: `src/dsv41/ds4_model.cu:7632-7635`。
- lane サービススレッドの起動: `src/dsv41/ds4_model.cu:3131-3156`。
- `strata-dsv41` のビルド条件と既定 OFF: `CMakeLists.txt:906-920`。
