# `STRATA_FOLLOW_LOGPOS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL の生成経路で、`STRATA_FOLLOW` によって指定された forced continuation を verifier の window で評価したとき、各 window の有効行について forced token の log-probability などを指定ファイルへ追記します。通常の argmax 生成のログ出力ではなく、forced continuation の品質調査用フックです。CUDA/HIP 側の対応はこの環境変数のソース参照からは確認できません。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | ログファイルを開かず、追記しない。 |
| 空文字 | `fopen("", "ab")` を試みる。通常は開けず `nullptr` となり、追記しない。エラーは表示しない。 |
| 空でないパス | バイナリ append モード (`"ab"`) で開く。開けた場合、既存内容を保持して末尾へ追記する。 |
| 開けないパス | `fopen` が返す `nullptr` のままになり、追記しない。明示的な警告やエラー処理はない。 |

パスの環境変数は SYCL 生成ループ内の関数ローカル `static FILE*` 初期化で一度だけ読みます。その初回評価後に環境を変更しても、このプロセスでは再読込しません。ファイルは明示的に閉じず、各出力後に `window_logprobs()` が `fflush()` します。`STRATA_LOGPOS_TOPK` は `window_logprobs()` 内の別の関数ローカル static で一度だけ読みます。

## 有効になる条件

- SYCL の `generate.cpp` にある通常の verify-window decode 経路で処理されること。
- `STRATA_FOLLOW` により forced continuation の token が読み込まれていること（未設定、またはファイルを開けない場合は `fol` が空）。
- `STRATA_FOLLOW_LOGPOS` のパスを開けること。

`STRATA_FOLLOW` のファイルはリクエスト開始時に整数 token ID として読み込まれ、読み込みに成功したファイルはその時点で削除されます。追記処理は `fol` が空でない場合に限られます。各 window では forced token を出力 token として設定した後、連続して受理された prefix の `a + 1` 行だけを `window_logprobs()` に渡します。入力 continuation が尽きると残りの target は `-1` とされ、verifier は負の target 行を出力しません。

## 実行時の詳細

出力はヘッダーなしのタブ区切りで、各有効行に次の列を記録します。

1. 生成位置 (`produced_n` からの位置)
2. forced token ID
3. forced token の log-probability
4. 最上位 token ID
5. 最上位 token の log-probability
6. forced token が最上位かを示す `0` または `1`
7. extra token の log-probability
8. extra token を除いた分布での forced token の log-probability

この呼出しは `extra_id=-1` を渡すため、7・8列目は `NAN` になります。`STRATA_LOGPOS_TOPK` が別途設定されている場合は、その上位 K token について `token_id:logprob` の列も後ろに追加されます。この値の parse 規則は `Verifier::window_logprobs()` にある別環境変数の処理に従います。

head logits がないなど verifier 側の失敗が `window_logprobs()` から返ると、生成経路は `ERR <内容>` を stdout に出して `1` を返します。`fprintf`、`fflush` の戻り値は検査されないため、追記後のディスク書き込み失敗を検知する処理はありません。ファイルを開けなかった場合は nullptr が使われ、`window_logprobs()` を呼ばないため、そこでの警告もありません。

## 根拠

- `sycl/src/program/generate.cpp:10729-10745`: forced continuation と `STRATA_FOLLOW_LOGPOS` の説明、および append モードでの static file open。
- `sycl/src/program/generate.cpp:11520-11536`: forced token の設定、受理 prefix の行数、log-probability 呼び出しと失敗時の `ERR` 出力。
- `sycl/src/program/generate.cpp:10734-10740`: forced continuation の読み込みと、読み込み後の入力ファイル削除。
- `sycl/src/core/verify.cpp:2582-2632`: invalid target 行の skip、タブ区切りの列、flush、および `STRATA_LOGPOS_TOPK` の上位 K 列。
