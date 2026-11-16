# `STRATA_UMA_DROP_PAGES`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`--serve` の起動処理で、CUDA 統合 GPU が全 expert を GPU cache に保持している場合に、モデルファイル側の expert の mapped pages を解放対象にするかを切り替える。環境変数が未設定なら有効で、`0` で始まる値なら無効。GPU cache の expert は残し、ファイル側にある同じデータのページを対象にする。実装は `src/program/generate.cpp` のサーバー初期化部と `src/core/expert_source.cpp` の `FileExpertSource::drop_cached_pages` にある（`src/program/generate.cpp:11438`, `12081-12120`; `src/core/expert_source.cpp:2651-2685`）。

## 値と判定

数値や真偽値への変換はしない。最初の読み取りは `getenv` が null か、先頭文字 `v[0]` が `'0'` かだけを判定する。したがって未設定は有効、空文字も有効、先頭が `0` の値（`0`, `0anything`, `00`）は無効、それ以外（`1`, `2`, `true`, `false`, 空白で始まる値を含む）は有効。大文字小文字、後続文字、数値としての妥当性は検査されない（`src/program/generate.cpp:12091-12094`）。

有効な場合、処理後に環境変数をもう一度読み、先頭が `2` のときだけ数値の診断行を出す（`src/program/generate.cpp:12110-12115`）。この判定も文字列全体を parse しないため、`2anything` も診断行の条件を満たす。

| ビルド・値 | unset | 設定時に処理が有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux CUDA（後述の実行条件も必要） | 有効 | 先頭が `0` 以外。例: 空文字、`1`、`2`、`true` | 先頭が `0`。例: `0`、`0anything` |
| HIP、Metal、Windows、または Linux の対象外 build | 対象コードが compile guard で除外される | なし | なし |

## 有効になる条件

- `--serve` の経路であること。処理は `if (o.serve)` のサーバー初期化内にある（`src/program/generate.cpp:11438`, `12080-12091`）。
- Linux CUDA build であること。コードは `__linux__` かつ `STRATA_USE_HIP`、`STRATA_HIP_GFX906`、`STRATA_GPU_METAL` が未定義の場合だけ compile される。Windows、HIP、Metal では環境変数を読まない（`src/program/generate.cpp:12090-12094`）。
- expert source が `FileExpertSource` (`srcp == &src`) で、GPU cache が全 layer・全 expert を保持し、単一 GPU で stage split がないこと（`src/program/generate.cpp:12091-12094`）。resident RAM arena (`srcp == &arena_src`) や部分的な GPU cache、複数 GPU ではこの呼び出しに入らない（`src/program/generate.cpp:8038-8046`, `8177-8179`, `8393`; `12091-12094`）。
- 現在の CUDA device の取得と `cudaDeviceGetAttribute(..., cudaDevAttrIntegrated, ...)` が成功し、統合 GPU と判定されること。別の GPU 属性、または取得失敗時はページ解放を呼ばない（`src/program/generate.cpp:12095-12118`）。
- `STRATA_FILE_TIER_IDLE` がこの条件に間接的に関係する。未設定または `atoi` の結果が 0 以外なら expert の常駐数を数えて `gpu_holds_all` を設定するが、`0`、空文字、数値変換結果が 0 の文字列では数えず、`gpu_holds_all` は初期値の false のままになる（`src/program/generate.cpp:9575-9594`）。

## 実行時の詳細

値は `--serve` 初期化中、prompt path の準備後に一度有効性を判定する。静的 cache は使わないが、この処理はリクエストごとの分岐ではなく起動時の分岐であり、起動後に環境を変更してもページ解放の実行可否は変わらない。処理後の診断レベル判定では別途 `getenv` を再実行する（`src/program/generate.cpp:12080-12120`）。子プロセスへの転送・上書きはこの処理にない。

統合 GPU 条件を満たすと、`drop_cached_pages` に callback を渡す。prompt path が借りる cache slot に載っている expert は保持し、それ以外の expert の mapped file pages を走査する。Linux 実装は blob 内の完全なページ範囲に `madvise(..., MADV_DONTNEED)` を呼び、その成功分について file offset に `posix_fadvise(..., POSIX_FADV_DONTNEED)` も呼び、成功したページ範囲のバイト数を返す。`unmapped_` の場合は 0 を返し、`madvise` が失敗した範囲は数えず、`posix_fadvise` の戻り値は無視する。expert cache 内のデータを削除する処理ではない（`src/program/generate.cpp:12099-12105`; `src/core/expert_source.cpp:2651-2685`）。

この変数の処理は token 選択や生成結果の値を設定しない。`generate.cpp` の近傍コメントは cache の bytes が同じで出力 bit は変わらないと説明しているが、ここで出力同一性を検査するコードはない（`src/program/generate.cpp:12081-12089`）。

## ログと測定値

ページ範囲の解放成功量が 0 より大きい場合、stderr に次の行を出す。

```text
strata serve: this GPU shares the system memory and holds every expert, so the model file's cached copy of them is given back.
```

`STRATA_UMA_DROP_PAGES` の先頭が `2` の場合は、解放量・所要時間・前後の CUDA free 値も stderr に出す。先頭が `2` でも解放量が 0 ならこの数値行は出ない。device 取得または統合属性の取得失敗時は `cudaGetLastError()` を呼ぶが、この箇所から警告・エラー行は出さない。ページ範囲の失敗も `drop_cached_pages` は個別に記録せず、失敗した分は返却量に含めない（`src/program/generate.cpp:12095-12118`; `src/core/expert_source.cpp:2651-2664`）。

ソースコメントには DGX Spark の画像読み込みに関する単発の所要時間例があるが、測定条件の詳細が揃った再現可能な測定値ではないため、一般的な性能値としては記載しない（`src/program/generate.cpp:12081-12089`）。`docs/DETAILS.md` に本変数の記載はない。

## 根拠

- `src/program/generate.cpp:11438`, `12080-12120` — サーバー経路、build guard、環境変数判定、統合 GPU 条件、解放呼び出し、ログ。
- `src/program/generate.cpp:8038-8046`, `8177-8179`, `8393` — file source と resident arena source の区別。
- `src/program/generate.cpp:9575-9594` — `STRATA_FILE_TIER_IDLE` と全 expert 常駐判定。
- `src/core/expert_source.cpp:2651-2685` — Linux でのページ範囲処理と他 platform の no-op。
