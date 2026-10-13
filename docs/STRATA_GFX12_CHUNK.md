# `STRATA_GFX12_CHUNK`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

Linux の HIP ビルドで、gfx1200/gfx1201（RDNA4）を使い、`strata generate --prefill auto` を指定したとき、auto prefill の最大チャンクを既定の 8192 から 16384 に引き上げる処理を止めるスイッチです。チャンクを必ず 16384 にする設定ではありません。選択可能な上限を変更し、後段の fit scan が GPU メモリと expert cache の貸し出し条件に合わせて実際のチャンクを決めます。

## 値と判定

`STRATA_GFX12_CHUNK` は `std::getenv()` で取得し、文字列全体や数値としては parse せず、先頭文字が `'0'` かだけを判定します（`src/program/generate.cpp:2166-2170`）。

| 値 | チャンク引き上げ判定 |
|---|---|
| unset | 許可 |
| 空文字 | 許可（先頭文字は `\0`） |
| 先頭文字が `0`（例: `0`, `0abc`） | 抑止 |
| その他（例: `1`, `false`, `abc`） | 許可 |

既定では、対象条件を満たす gfx12 の bare `--prefill auto` で `prefill_auto_max` と初期 `prefill_chunk` がともに 16384 になります。`STRATA_GFX12_CHUNK` の先頭文字が `0` の場合は引き上げ処理を通らず、既定の 8192 のままです。

## 有効になる条件

次の条件がすべて必要です。

- `STRATA_USE_HIP` でコンパイルされ、かつ `_WIN32` ではないこと。
- 指定が bare `--prefill auto` であること。`--prefill N`、`--prefill auto:N`、または `STRATA_PREFILL_AUTO_MAX` が設定された bare `auto` は対象外です。
- デバイス 0 のプロパティ取得が成功し、アーキテクチャ名が gfx1200 または gfx1201（任意の `:feature` suffix は許容）であること。
- この変数と `STRATA_GFX12_DEFAULTS` のどちらも、先頭文字が `0` でないこと。

`STRATA_GFX12_DEFAULTS=0` もこのチャンク引き上げを抑止します。加えて同変数は gfx12 向けの別の既定スイッチ群も抑止します（`src/program/generate.cpp:2165-2170`, `src/core/arch_defaults.cpp:12-30`）。

## 実行時の詳細

`--prefill` の引数を読む際、bare `auto` で `STRATA_PREFILL_AUTO_MAX` が未設定なら、まず `prefill_auto_max` は 8192 になります。変数が設定されていれば、値は `atoll` に渡され、その後の上限は 8192 / 16384 / 32768 のいずれかに丸められます。空文字も「設定済み」なので bare-auto の gfx12 引き上げ対象から外れます（`src/program/generate.cpp:1946-1954,1962-1965`）。

引数処理後、Linux HIP かつ `prefill_auto_bare` の場合にこの変数を読みます。対象 GPU で引き上げが実行されると stderr に次の行が出ます。

```text
strata generate: gfx12: --prefill auto may take chunks up to 16384 (STRATA_GFX12_CHUNK=0 keeps 8192)
```

この判定は引数処理後に一度行われます。プロセス実行中に環境変数を変更して再評価するコードはありません。gfx12 判定ではデバイス 0 のみを問い合わせます。問い合わせに失敗した場合は引き上げず、`cudaGetLastError()` でエラー状態を読み出します（`src/program/generate.cpp:2160-2175`）。

上限は `auto_ceiling` に使われ、コンテキスト長を超えない範囲で、後段の auto scan が適合するチャンクを探します。expert cache が貸せる量やリング予算に収まらなければ、選ばれるチャンクは 16384 より小さくなります（`src/program/generate.cpp:6296-6315,6337-6345,7017-7045`）。

## 根拠

- `src/program/generate.cpp:1946-1954,1962-1965` — `--prefill` と `STRATA_PREFILL_AUTO_MAX` の判定および初期上限。
- `src/program/generate.cpp:2160-2175` — Linux HIP 条件、環境変数の先頭文字判定、gfx12 判定、上限変更と stderr ログ。
- `include/strata/kernels/gfx_arch.hpp:15-20,35-36` — gfx arch 名の完全一致（suffix は `:` から許容）と gfx12 対象。
- `src/program/generate.cpp:6296-6315,6337-6345,7017-7045` — auto 上限と適合チャンクの選択。
- `src/core/arch_defaults.cpp:12-30` — 関連する `STRATA_GFX12_DEFAULTS` が別の gfx12 既定スイッチ群を制御する箇所。
- `docs/DETAILS.md:1947` — bare `--prefill auto` の gfx12/Linux 既定引き上げと抑止変数の説明。記載は上記の実装条件と一致します。
