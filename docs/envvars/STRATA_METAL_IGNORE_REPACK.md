# `STRATA_METAL_IGNORE_REPACK`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal エンジンの decode window 初期化時に、モデルファイルと同じディレクトリでモデルの repack または setup の準備が実行中と検出された場合でも、起動拒否を解除します。この検査は Metal エンジンの `Window::init()` にあり、通常の CUDA/HIP エンジンにはこの参照はありません。

## 値と判定

環境変数の値は整数として parse せず、`std::string` として文字列全体を比較します。検出した実行中プロセスがある場合に限り、値が厳密に `1` なら拒否条件を解除します。

| 値 | 実行中プロセスを検出した場合 |
|---|---|
| 未設定 | 初期化を拒否 |
| 空文字 | 初期化を拒否 |
| `1` | この検査による拒否を解除し、次の初期化処理へ進む |
| `0`、`true`、`01`、`1 `、その他 | 初期化を拒否 |

有効値の判定に大文字小文字や数値変換は関係せず、空白も含めて完全一致が必要です。該当変数は `getenv()` で毎回参照され、static cache されません。window が未初期化で `Window::init()` が再度呼ばれれば、その時点の環境値が使われます。既に window が ready の場合、`window_init()` は `init()` を呼ばないため、この検査も値の再評価も行いません。

根拠: `metal/src/engine/window.cpp:409-425,2474-2485`。

## 有効になる条件

変数が初期化を左右するのは、`repack_pid_running(shard1)` が生きた別プロセスの PID を返したときだけです。同関数はモデル shard の親ディレクトリ内を調べ、名前が `.preparing.lock` と一致するファイル、または末尾が `.repack.lock` のファイルをロック候補とします。ファイル先頭から `%ld` で PID を読み、正の PID で自プロセスの PID と異なり、`kill(pid, 0)` が成功するか `errno == EPERM` なら実行中として返します。したがって、ロック候補がない、PID を読めない、PID が正でない、自プロセス自身の PID、またはプロセスが存在しない場合は、この環境変数にかかわらず初期化拒否は発生しません。

値を `1` にしても、repack や setup を停止・待機させたり、モデルファイルの整合性を検証したりはしません。エンジンはそのまま `f_.open(shard1, err)` 以降の初期化へ進みます。ほかの初期化条件やファイル読み込みが失敗すれば、別の理由で起動できないことがあります。

根拠: `metal/src/engine/window.cpp:392-405,420-425`。

## 実行時の詳細

拒否時は `Window::init()` が `err` に `metal window: a model repack or setup's preparation is running here (pid <PID>): the engine is not started beside it (it froze a 128 GB Mac twice); wait for it to finish, or set STRATA_METAL_IGNORE_REPACK=1` を設定して `false` を返します。`window_init()` はその失敗を呼び出し元に返します。Metal 検証器の初期化と Metal prefill の初期化はいずれもこの window 初期化経路を使います。

repack 用 `.repack.lock` の作成元は `metal/tools/metal_repack.py`、setup 準備中の `.preparing.lock` の作成元は `metal/setup_mac.py` です。setup 側もモデル準備中のエンジン起動を避ける仕組みを持ちますが、この環境変数自体を読むのはエンジン側です。

## 根拠

- 環境変数の唯一の実読み取りと起動拒否: `metal/src/engine/window.cpp:420-425`。
- 対象ロック名、PID の読み取りと生存判定: `metal/src/engine/window.cpp:392-405`。
- window 初期化と失敗伝播: `metal/src/engine/window.cpp:2474-2489`、`src/core/verify.cpp:577-580`、`src/prefill/prefill.cpp:1082-1090`。
- ロック作成元: `metal/tools/metal_repack.py:26-29`、`metal/setup_mac.py:415-416,610-625`。
- `docs/MAC.md:199` は `=1` で準備中の起動を許す設定として記載しています。性能値はこの変数の効果として示されていません。
