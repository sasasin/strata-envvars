# `STRATA_DROP_CACHE_ON_EXIT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリや OS の内部動作は対象外。

## 役割

`strata serve` の終了処理で、エンジンが使っていたモデルファイルに対し、ファイルキャッシュを解放するよう `posix_fadvise(..., POSIX_FADV_DONTNEED)` を呼び出す opt-in です。サーバーの通常の終了処理では呼ばれず、終了中にもう一度 Ctrl+C が押され、close 処理が `KeyboardInterrupt` を受けた経路でのみ呼び出されます。

## 値と判定

| 条件 | 判定 |
|---|---|
| unset、空文字、空白だけ | 無効 |
| 前後空白を除去し、小文字化した値が `1` / `true` / `yes` / `on` | 有効 |
| それ以外（例: `0`, `2`, `enabled`, `01`） | 無効 |
| Windows (`os.name == "nt"`) | 値にかかわらず無効 |

文字列全体に対して `.strip().lower()` を適用してから集合と完全一致で比較します。したがって大文字小文字は区別せず、`" TRUE "` は有効ですが、`"true extra"` は無効です。数値変換はしません。既定は無効で、CLI 引数や設定ファイルによる上書きはありません。`enabled()` は呼び出しごとに `os.environ` を参照し、static cache はありません。

## 有効になる条件

- `serve/server.py` のサーバー終了処理が `KeyboardInterrupt` を受けること。通常の Ctrl+C で始まる shutdown ではなく、終了処理中に再度 Ctrl+C が押された場合の例外ハンドラーに置かれています。
- その例外ハンドラーで `engine.proc` が存在し、現在の OS が Windows でないこと。
- `drop_after_exit()` の時点でエンジンのプロセスがすでに終了していること。`proc.poll()` が `None`（実行中）なら何もせず 0 を返します。
- `os.posix_fadvise` が利用可能であること。ない場合は 0 を返し、ファイルを処理しません。

したがって `STRATA_DROP_CACHE_ON_EXIT=1` だけでは、通常のサーバー停止時にキャッシュ処理は実行されません。また、終了処理中にプロセスへ `kill()` を送った直後に関数が呼ばれるため、その時点で `poll()` がまだ実行中を返す場合も処理はスキップされます。

## 実行時の詳細

例外ハンドラーはエンジンのプロセスに `kill()` を送り、`serve.cache_drop.drop_after_exit(engine)` を呼びます。モジュールは `engine.spawn` の引数から `--native`, `--pack`, `--mmproj`, `--model` の直後の値をファイル候補として集め、候補がなければ `engine.model_path` を使います。候補がディレクトリなら再帰的に通常ファイルを列挙し、各ファイルを読み取り専用で開いて全範囲に `POSIX_FADV_DONTNEED` を指定します。存在しないパス、列挙時や open 時の `OSError` はそのファイルをスキップします。advice 呼び出しで `OSError` が起きた場合も数えません。

`drop_after_exit()` は、処理したファイル数（advice 呼び出しが `OSError` を出さなかった件数）を返し、0 件の場合も含めて `[strata] STRATA_DROP_CACHE_ON_EXIT: released the page cache of N model files` を stdout に出します。advice の発行は Strata が行う処理ですが、OS が実際にいつ・どの程度キャッシュを解放するかは Strata のコードから保証できません。呼び出し全体で例外が発生した場合は、サーバー側の外側の handler が `[strata] could not release the model files' cache: ...` を出して終了を続けます。

`src/core/expert_source.cpp` にも同じ変数を案内する文字列がありますが、ここではメモリ情報に付けるヒント文を組み立てているだけで、環境変数は読み取りません。実際の値判定と処理は `serve/cache_drop.py` にあります。

## 根拠

- `serve/cache_drop.py:14-16` — 値の取得、OS 条件、許可文字列と正規化。
- `serve/cache_drop.py:19-33` — 通常ファイルとディレクトリの列挙。
- `serve/cache_drop.py:36-54` — `posix_fadvise` の有無、対象ファイルを開いて advice を呼ぶ処理。
- `serve/cache_drop.py:57-70` — 子プロセス終了確認、対象パス選択、ログ出力。
- `serve/server.py:8457-8470` — shutdown の closer 中に再度 `KeyboardInterrupt` を受けた際の kill、cache drop 呼び出し、エラー処理。
- `serve/server.py:966-972` — `StrataEngine` が起動引数と `model_path` を保持する処理。
- `src/core/expert_source.cpp:150-160` — 環境変数を読み取らない案内文。

`docs/DETAILS.md` にはこの変数の説明や測定値は見つかりませんでした。挙動の記述は上記の実装に基づき、キャッシュ解放の実効性や速度・メモリ量の改善は測定・保証していません。

