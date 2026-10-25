# `STRATA_METAL_STREAM_FAKE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal engine の expert streaming で、常駐していない routed expert を実際に SSD から読み込まず、arena の slot 0 を指すようにして計測するためのフックです。値を有効にすると expert の内容が正しくならないため、通常の推論結果を得る設定ではありません。実装コメントも `timing only (WRONG answers)` と明記しています。

## 値と判定

`stream.cpp` の `env_int(name, default)` は `getenv()` の値が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` の結果を使います。この変数の既定値は `0` です。

| 環境変数の値 | `atoi` の結果 | fake 処理 |
|---|---:|---|
| 未設定、空文字 | 0（既定値） | 無効 |
| `0`、`00`、`0suffix`、数値として解釈できない文字列 | 0 | 無効 |
| `1`、`-1`、`2suffix` など、先頭の整数部分が非ゼロ | 非ゼロ | 有効 |

`atoi` は文字列全体の厳密な数値検証をしません。先頭の空白と符号を許し、数値部分の後ろにある文字列は無視します。たとえば `2abc` は非ゼロとして扱われ、`abc2` は 0 です。空白だけの値も `atoi` が 0 を返すため無効です。

根拠: `metal/src/engine/stream.cpp:27-30,161-163`。

## 有効になる条件

- Apple Metal engine の `Window::init()` が expert streaming 経路を選んだ場合に限ります。`ExpertStream::wanted()` が明示的な `STRATA_METAL_STREAM=1` を受けるか、既定のサイズ判定で streaming を選ぶと、この経路で `ExpertStream::open()` が呼ばれます。`STRATA_METAL_STREAM=0` などで streaming が選択されない場合、この変数は読み取られず効果もありません。
- 対象 `Window::init()` は Qwen3.8-Flash-Next の所定 geometry（48 layers、512 experts など）を要求し、合わない場合は初期化を失敗させます。
- `open()` 時に値を一度読み、`ExpertStream` インスタンスの `fake_` に保存します。実行中に環境を変更してもそのインスタンスには反映されません。モデルを新たに初期化して別の `ExpertStream` を作る場合は再評価されます。

`STRATA_METAL_STREAM` は streaming の選択を制御する別変数です。この調査対象変数単独で streaming を開始させることはありません。

根拠: `metal/src/engine/stream.cpp:33-48,60-63,161-163`; `metal/src/engine/window.cpp:435-458`。

## 実行時の詳細

各層の routed expert を処理する `ExpertStream::at_layer()` は、選択された expert のうち現在 arena にないものについて、通常は slot を割り当てて読み込み要求を投入し、読み込み完了を待ってから `smap_` を使う GPU 処理へ進みます。`fake_` が有効な場合は、未常駐 expert ごとに `smap_` の該当要素を `code_[0]`（slot 0 の arena address）へ差し替え、時間を記録してそこで戻ります。expert の読み込み、待機、通常経路の miss 処理や次層の read-ahead は実行しません。既に常駐している expert の対応表はこの分岐では変更しません。

したがって未常駐 expert が選ばれると、要求された expert とは別の slot 0 のバイト列を expert kernel が参照し、出力の正しさは保証されません。slot 0 の読み込み内容・割当状態を前提とする計測用フックであり、正確な token 出力、性能の通常比較、利用者向け推論には適しません。ソースにはこの変数固有の警告ログやエラー終了処理はありません。

根拠: `metal/src/engine/stream.cpp:617-638`; `metal/src/engine/stream.h:7-12,57-65`; `metal/src/engine/window.cpp:301-306`。

## 根拠

- `metal/src/engine/stream.cpp:27-30` — 空値・未設定時の既定値、および `atoi` による変換。
- `metal/src/engine/stream.cpp:161-163` — `STRATA_METAL_STREAM_FAKE` の読み取りと既定 OFF。
- `metal/src/engine/stream.cpp:617-638` — fake 分岐で slot 0 を指定し、読み込み処理より前に戻る箇所。
- `metal/src/engine/window.cpp:435-458` — 対応 geometry の確認、streaming の選択と `ExpertStream` の初期化。
- `metal/src/engine/window.cpp:301-306` — engine の layer 処理から `ExpertStream::at_layer()` を呼ぶ箇所。
- `metal/src/engine/stream.h:7-12` — streaming arena の `smap` を expert kernels が参照する設計の説明。
