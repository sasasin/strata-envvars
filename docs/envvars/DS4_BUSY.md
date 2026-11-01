# `DS4_BUSY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Metal 版 `strata_ds4` の DeepSeek 実行で、CPU 側 expert の処理中に GPU を短時間動作させ続ける補助 kernel を止めるためのスイッチです。`DS4_BUSY` はこの処理を有効にする値を選ぶのではなく、値が文字列 `0` と完全一致した場合に限って無効化します。

## 値と判定

| 環境変数の状態 | `ds4_busy_begin()` の判定 |
|---|---|
| 未設定 | 有効（無効化しない） |
| 空文字 | 有効（無効化しない） |
| 文字列がちょうど `0` | 無効。関数は直ちに戻る |
| その他の設定値 | 有効（例: `00`, `0 `, `false`, `1`） |

数値変換や真偽値 parse はなく、`std::string` と `"0"` の完全一致比較です。判定結果は関数内の `static const bool` に保存され、最初の呼び出しで一度だけ評価されます。その後プロセス内で環境値が変わっても再評価されません（`metal/src/mtl_rt.mm:235-237`）。

## 有効になる条件

- `STRATA_METAL` が定義された DeepSeek Metal 経路で呼び出される場合に限り、`ds4_model.cu` からこの関数が呼ばれます。通常の CUDA/HIP 経路にはこれらの呼び出しがありません（`src/dsv41/ds4_model.cu:41-45,10555-10566`）。
- Metal ターゲット `strata_ds4` は `ds4_model.cu` と `metal/src/mtl_rt.mm` を含み、後者を `STRATA_DS4_RUNTIME=1` 付きでコンパイルします（`metal/CMakeLists.txt:138-165`）。
- 通常の呼び出しは、対象 layer に CPU 側 expert がある `!ents.empty()` の区間で CPU expert 計算を行う間です。`DS4_BUSY=0` ならこの区間で補助 kernel を開始しません（`src/dsv41/ds4_model.cu:10555-10566`）。
- 別変数 `DS4_BUSY_ALL` が設定されている場合、Metal 経路では `forward()` の全体を囲う開始・終了呼び出しも行われます。これは `DS4_BUSY` とは別の変数ですが、`DS4_BUSY=0` はその開始呼び出しも無効化します（`src/dsv41/ds4_model.cu:9693-9700`）。

## 実行時の詳細

有効な `ds4_busy_begin()` は初回に Metal device からインライン Metal shader をコンパイルして pipeline を作り、別 command queue と共有メモリの flag を用意します。準備に失敗して `g_busy.ok` が立たない場合は開始せず、その失敗を出すログやエラー処理はこのコードにありません。開始時には前回の command buffer があれば完了を待ち、flag を 0 にして spin kernel を dispatch します。対応する `ds4_busy_end()` は flag を 1 にして spin を抜けさせます（`metal/src/mtl_rt.mm:239-289`）。

dispatch 幅や spin 回数は別変数 `DS4_BUSY_W` と `DS4_BUSY_CAP` が決めます。`DS4_BUSY` 自身には CLI 引数、設定ファイル、別環境変数による値上書きはありません。この実装に `DS4_BUSY` に関するログ出力、終了コード変更、失敗通知もありません。

## 根拠

- 候補一覧の `DS4_BUSY` 全参照は `metal/src/mtl_rt.mm:222,235-237` です。行 222 はコメント、行 236 が環境から値を読む唯一の箇所です。
- `DS4_BUSY_ALL` による `forward()` 全体の囲い込み: `src/dsv41/ds4_model.cu:9693-9700`。
- CPU expert 処理区間からの開始・終了呼び出し: `src/dsv41/ds4_model.cu:10555-10566`。
- Metal DeepSeek ターゲットのビルド構成: `metal/CMakeLists.txt:138-165`。
