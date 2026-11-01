# `STRATA_METAL_STREAM_FAKE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal backend の SSD streaming 経路で、未常駐 expert の読み込みを省略して処理時間を測る開発・計測用フックです。未常駐 expert の参照先を arena の slot 0 に差し替えるため、正しいモデル出力を得る設定ではありません。実装コメントも `timing only (WRONG answers)` と明記しています。

この変数が効くのは `ExpertStream` が使われるときだけです。Metal window は `STRATA_METAL_STREAM=1` なら streaming を選び、`=0` なら選びません。未設定などの auto 判定では、モデルの重みが GPU working set と余裕分に収まらない場合に streaming を選択します。streaming を選ばなければ `ExpertStream::open()` が呼ばれず、この変数も読み込まれません（`metal/src/engine/stream.cpp:33-48`, `metal/src/engine/window.cpp:541-548`）。

## 値と判定

`env_int()` は値が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` で整数変換します。fake の既定値は `0` で、変換結果が `0` 以外なら有効です（`metal/src/engine/stream.cpp:27-30,162`）。

| 環境値 | 判定 |
|---|---|
| 未設定、空文字 | 既定値 `0`。無効 |
| 数値変換結果が `0` | 無効。例: `0`, `false`, `junk`, `0tail` |
| 数値変換結果が非 `0` | 有効。例: `1`, `-1`, `2`, `1tail` |

文字列全体の妥当性検査、空白除去、範囲制限はありません。`atoi` が先頭から整数に変換できない文字列は `0` になり、整数の後ろに文字があっても変換できた先頭部分で判定します。CLI 引数による上書きや、別環境変数との値の優先順位はこの実装にはありません。`STRATA_METAL_STREAM` は値の優先順位ではなく、そもそもこの streaming 実装を使うかを決めます。

## 有効になる条件

- Metal backend を含む macOS 向け engine で実行する必要があります。Metal engine のソースは `metal/CMakeLists.txt` で `metal/src/engine/*.cpp` から構成されます（`metal/CMakeLists.txt:71-89,110-124`）。
- `STRATA_METAL_STREAM` の明示値または auto 判定により `ExpertStream` が選ばれている必要があります。streaming が無効なら、この環境変数の値にかかわらず効果はありません（`metal/src/engine/stream.cpp:33-48`; 呼び出し側 `metal/src/engine/window.cpp:541-548`）。
- streaming の arena が作成され、モデル実行中に各 layer の host 側処理 `Window::at_cut()` から `ExpertStream::at_layer()` が呼ばれる経路で作用します（`metal/src/engine/window.cpp:382-395,1408-1410`）。サーバーモードか CLI か自体を判定する条件はありません。

## 実行時の詳細

値は `ExpertStream::open()` の初期化中に一度読み、`fake_` メンバーへ保存します。各 layer やリクエストで環境変数を読み直す処理はないため、実行開始後に環境値を変更しても既存の `ExpertStream` には反映されません（`metal/src/engine/stream.cpp:60-63,149-163`; メンバー定義 `metal/src/engine/stream.h:120-121`）。

fake が有効でも arena の初期化・profile 上位 expert の読み込みは通常どおり行われます（`metal/src/engine/stream.cpp:371-413,481-515`）。各 layer では、ルーティングされた expert ID のうち `where_` に常駐していないものだけ、`smap` 上の値を `code_[0]` に差し替えて戻ります。通常経路で行う miss の slot 確保、SSD 読み込みの投入、読み込み完了待ち、layer ごとの read-ahead はこの分岐では行いません。すでに常駐している expert の対応は差し替えません（`metal/src/engine/stream.cpp:617-636`; 通常の miss・待機・read-ahead 経路 `metal/src/engine/stream.cpp:637-714`）。その結果、未常駐 expert の計算は要求された expert のデータを使わず、誤った出力になります。

この分岐専用の警告、エラー、終了処理はありません。処理時間の計測値は通常の window 集計・終了時の stream report に出ますが、fake を有効にしたことを示す表示はありません（`metal/src/engine/stream.cpp:631-636,803-821`; report の呼び出し `metal/src/engine/window.cpp:383-389,1430-1432,1530-1532`）。初期 arena の読み込み失敗など、fake 分岐より前の通常の初期化失敗は別に起こりえます。

## 根拠

- 候補名の全参照検索では、環境値を読む Strata 実装は `metal/src/engine/stream.cpp:162` の一箇所でした。値変換 helper は同ファイルの `:27-30` です。
- fake 分岐と通常の expert 読み込み処理: `metal/src/engine/stream.cpp:617-714`。
- `ExpertStream` の生成・初期化条件と layer callback: `metal/src/engine/window.cpp:382-395,541-548`。
- Metal engine の CMake 構成: `metal/CMakeLists.txt:71-89,110-124`。
