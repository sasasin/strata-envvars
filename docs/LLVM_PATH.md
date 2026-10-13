# `LLVM_PATH`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリ自身が `LLVM_PATH` をどう使うかは対象外。

## 役割

Strata の `serve/server.py` は、HIP backend 用の子プロセス環境を作るとき、`LLVM_PATH` が指すパスの存在を確認します。値を LLVM の場所として解釈したり、別の LLVM パスを探したりする処理ではありません。空でない値のパスが存在しない場合に、その変数を子プロセスへ渡さないよう削除します。

この処理はサーバーの HIP 環境ガードであり、候補一覧に名前があるだけで通常の engine が直接読む設定だとは確認できませんでした。対象ソースでは `serve/server.py` のこのガード以外に `LLVM_PATH` の参照はありません。

## 値と判定

Strata は値を数値や真偽値として parse せず、trim もしません。Python の `env.get("LLVM_PATH")` で値を取得し、Python の真偽値判定と `Path(v).exists()` で分岐します。

| 子環境の値 | HIP 環境ガードの処理 |
|---|---|
| キーがない | 何もしない |
| 空文字 `""` | falsy のため何もしない。キーは残る |
| 空でない値でパスが存在する | 値を変更せず残す |
| 空でない値でパスが存在しない | `LLVM_PATH` を子環境から削除し、stderr に `LLVM_PATH=<値> does not exist: not passed to the engine` と出す |

相対パスはサーバープロセスの現在の作業ディレクトリを基準に `Path.exists()` で確認されます。大文字小文字や値の形式を Strata が個別に検査するコードはありません。パスの存在確認で発生した例外をこのガードが捕捉する処理もありません。

## 有効になる条件

- `child_env(cfg)` が呼ばれ、`cfg["backend"] == "hip"` の場合だけ `hip_env_guard(env, cfg)` が呼ばれます。CUDA など別 backend では、Strata のこのガードによる存在確認・削除・ログ出力はありません。
- `child_env` はまずサーバーの `os.environ` を複製し、その後 `cfg["env"]` にある値を文字列化して上書きします。したがってガード対象は、親プロセスから継承した値または設定の `env` が上書きした値です。専用 CLI 引数での優先順位や補完処理はありません。
- 通常起動では `child_env` の戻り値が Strata engine に渡されます。レプリカ起動でも各 replica の設定から `child_env` を作り、その値を各 engine に渡します。
- vision encoder が設定されている起動経路では、同じ環境を元に `vision_env` が環境を作ります。HIP backend の場合に `CUDA_VISIBLE_DEVICES` を変更する処理はなく、`LLVM_PATH` はそのまま残るか、先行する HIP ガードで削除済みです。

## 実行時の詳細

`child_env` は `dict(os.environ)` を作成し、設定 `env` の各キー・値を適用した後、HIP backend なら `hip_env_guard` を呼びます。ガードは `HIP_PATH`、`HIP_DEVICE_LIB_PATH` と同じループで `LLVM_PATH` を検査します。`v` が空でない場合に限り `Path(v).exists()` を調べ、存在しないと `del env[k]` で子環境から外します。サーバー自身の `os.environ` を変更するコードではありません。

`StrataEngine` は受け取った環境辞書を `subprocess.Popen(..., env=env)` に渡します。ガードの変更メッセージは stderr に `strata serve: AMD: ` を付けて出力されます。ログ文字列はエンジン起動前のサーバー側処理で組み立てられます。この環境辞書の作成時に確認するため、サーバー起動後に親環境だけを変更しても、すでに起動した engine の環境辞書は更新されません。engine 再起動時は `StrataEngine` が保存した起動引数と環境で再起動します。

## 文書との照合と制限

`docs/TROUBLESHOOTING.md` は、存在しない ROCm ディレクトリを指す `LLVM_PATH` などをサーバーが engine 起動前に除くと説明しています。現行実装でも該当パスを子環境から削除し、stderr に変更理由を出す点は一致します。文書の AMD runtime のクラッシュ原因や回避効果は Strata のコードから独立に検証していないため、ここでは Strata が実際に行う環境処理だけを記載しました。

## 根拠

- `serve/server.py:2622-2639` — 親環境の複製、設定 `env` による上書き、HIP backend のガード呼び出し。
- `serve/server.py:2650-2680` — `LLVM_PATH` を含むパス検査、削除、stderr メッセージ。
- `serve/server.py:649-652,697-699` — engine の起動環境を保存し、`Popen` へ渡す処理。
- `serve/server.py:6222-6238,6375-6426` — replica 起動と通常の Strata engine 起動での `child_env` 使用。
- `serve/server.py:2683-2696,6392-6393` — vision encoder 用環境の生成と利用。
- `docs/TROUBLESHOOTING.md:148-153` — AMD Windows のトラブルシュート説明。
