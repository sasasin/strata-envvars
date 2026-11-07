# `STRATA_METAL_WPF_MIB`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

Metal decode window が、次に使う重み tensor の先頭を GPU に先読みさせる dispatch を追加します。単位は MiB で、各 tensor について要求量と tensor の byte 数の小さい方を読みます。先読み kernel は読み込んだ値を計算結果へ渡さず、通常の推論計算結果を変えない設計です。既定値は 0 MiB（無効）です。

## 値と判定

値は `std::atoi` で整数に変換し、結果を `size_t` に変換してから `1048576` 倍します。文字列全体の妥当性検査、範囲検査、clamp、警告はありません。

| 環境変数の値 | 結果 |
|---|---|
| 未設定 | 0 MiB、無効 |
| 空文字、数値に変換できない文字列 | `atoi` が 0 を返すため無効 |
| `N`（`atoi` が正の整数 N を返す文字列） | 各対象 tensor の先頭 `min(N × 1,048,576, tensor の byte 数)` byte を対象にする。数値の後ろの文字は `atoi` に無視される（例: `4xyz` は 4） |
| `0` または `atoi` の結果が 0 | 無効 |
| 負数 | 0 には clamp されない。負の `int` を先に `size_t` に変換して乗算するため、通常は非常に大きい要求量となり、tensor 全体まで要求し得る |

先頭の空白や符号は `atoi` の変換規則に従います。`atoi` が `int` の範囲外の入力に対して返す値は実装で検証しておらず、このコードから安全な値は定められません。変数を複数回読み直す処理や CLI による上書きはありません。

## 有効になる条件

- `STRATA_GPU_METAL` を定義した Metal build で、Metal verifier が decode window を初期化する経路が対象です。CUDA/HIP/CPU の実装にはこの環境変数の読み取り箇所がありません（`src/core/verify.cpp:900-902`）。
- `Window::init()` は Qwen3.8-Flash-Next の形状（48 層、所定の埋め込み等、expert 数は標準または半数）を要求します。形状が異なる場合は別の初期化失敗経路となり、この window は使われません（`metal/src/engine/window.cpp:670-680`）。
- 値の読み取りは `Window` のメンバー初期化時です。プロセス開始後に環境を書き換えても、その `Window` インスタンスでは反映されません。window shape ごとの dispatch graph は初回構築後にキャッシュされて再利用されます（`metal/src/engine/window.cpp:452,1447-1475`）。
- 値が 0 なら `wpf_add()` が何も登録しないため dispatch は追加されません。正の値なら各 layer の注意機構側と MoE 側で列挙した重みが対象です。注意機構では通常層（層番号 `% 4 != 3`）の `attn_qkv` / `attn_gate`、4 層ごとの層では `attn_q`、MoE 側では `ffn_gate_inp` / `ffn_gate_shexp` / `ffn_up_shexp` を登録します（`metal/src/engine/window.cpp:1056-1060,1191-1193`）。
- 見つからない tensor は `wpf_add()` では登録されません（`metal/src/engine/window.cpp:453-456`）。この環境変数専用のサーバーモード、CLI option、他環境変数による優先順位や無効化条件は確認できません。

## 実行時の詳細

`wpf_add()` は名前から GGUF tensor を検索し、その offset と要求 byte 数（tensor サイズを上限とする）を `wpf_next_` に蓄積します。Hyper-connection の read dispatch を組み立てる `gr_read()` は、`gr_up` の後に各登録 tensor につき `wpf` dispatch を追加します。dispatch は `W_` の tensor offset から `bytes / 16` 個の `uint4` を読み、grid-stride loop でデータを参照します。16 byte 未満の端数は対象外です（`metal/src/engine/window.cpp:453-456,1003-1023`; `metal/kernels/gr.metal:281-288`）。

`gr_up` の直後に `nb_ = true` としてから `wpf` を追加するため、この dispatch の直前には buffer memory barrier を置きません。Metal の concurrent compute encoder は `barrier` が設定された dispatch の前だけ barrier を挿入します。したがって prefetch dispatch は直前の独立 dispatch と重なれるように登録されます（`metal/src/engine/window.cpp:1012-1021,280-282`; `metal/src/mtl_rt.h:122-124`; `metal/src/mtl_rt.mm:995-1007`）。登録後に `wpf_next_` は空になります。初回 window の graph 構築時に追加された dispatch は graph cache に含まれ、cache hit 時も再実行されます（`metal/src/engine/window.cpp:1447-1475,1531-1558,1610-1612`）。

Metal kernel は読み込んだ `uint4` の XOR が特定値のときだけ scratch buffer に `1` を書きます。Strata の後続処理がこの flag を読む箇所は確認できません（`metal/kernels/gr.metal:281-288`; `metal/src/engine/window.cpp:450-456,1012-1023`）。この設定に固有の stdout/stderr ログ、無効値警告、失敗処理はありません。GPU command buffer 自体が失敗すれば共通経路が `mtl: command buffer failed: ...` を stderr に出して exit code 5 で終了しますが、これはこの環境変数固有の検査ではありません（`metal/src/mtl_rt.mm:1014-1018`）。

## 根拠

- 唯一の実コード読み取りと値の変換: `metal/src/engine/window.cpp:448-456`。
- 対象 tensor とレイヤー順: `metal/src/engine/window.cpp:1056-1060,1191-1193`。
- prefetch dispatch の作成と barrier 指定: `metal/src/engine/window.cpp:1003-1023,280-282`。
- shader が読むデータと書き込み条件: `metal/kernels/gr.metal:281-288`。
- Metal backend の verifier 接続と対象モデル形状: `src/core/verify.cpp:900-902`; `metal/src/engine/window.cpp:670-680`。
- dispatch graph の実行と失敗時の終了: `metal/src/engine/window.cpp:1406-1412,1447-1475,1531-1558,1610-1612`; `metal/src/mtl_rt.mm:995-1019`。
- `docs/DETAILS.md` と `docs/` 以下の設計資料には、この変数の追加説明や測定値は見つかりませんでした。
