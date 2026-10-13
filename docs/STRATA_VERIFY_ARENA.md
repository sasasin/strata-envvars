# `STRATA_VERIFY_ARENA`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

SYCL 実装で expert arena の読み込みが完了した後、読み込んだ expert データ全体の FNV-1a 64-bit checksum とサイズを stderr に出す診断用フックです。値を検証値と比較したり、読み込み結果を変更したりはしません。実装コメントも用途を tests としています。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | checksum を出さない |
| 設定済み（空文字を含む） | 値の内容を問わず checksum を出す |

実装は `std::getenv("STRATA_VERIFY_ARENA") != nullptr` のみを判定します。`1` との比較や数値変換はなく、`0`、`false`、空文字も設定されていれば有効です。

## 有効になる条件

この読み取りは SYCL ツリーの `ArenaExpertSource::open()` にだけあります。SYCL の生成処理が `--stream-experts` でも `--mmap-experts` でもない経路で arena を開く場合に到達します。streaming は `GgufExpertSource` を使い、`--mmap-experts` は別の `FileExpertSource` を使うため、どちらの経路でもこの checksum 出力箇所は通りません。また `STRATA_ARENA_MMAP` が有効で、既存の `experts.bin` が padded arena サイズなら、`ArenaExpertSource::open()` はファイルを map した時点で早期 return するため checksum を出しません。初回 load など mmap の早期 return を通らない経路では判定箇所まで進みます。

さらに、arena の予約、expert の読み込み、および読み込み byte 数の確認が成功した後に判定されます。読み込み失敗や `st.bytes != want` の場合は先に `open()` が失敗して戻るため、checksum は出ません。`STRATA_ARENA_MMAP` による既存 arena の早期 map 経路には到達しません。

## 実行時の詳細

`open()` が成功した読み込みのたびに環境変数を読み直します。値を `static` に保存していないため、プロセス内で環境を変更した場合は次回の `open()` に反映されます。子プロセスへの転送や上書き処理はありません。

設定されていれば、読み込み先 `a->data()` の先頭から `want` byte を FNV-1a 64-bit でハッシュし、次の形式を stderr に出します。

```text
strata generate: expert arena checksum %016llx (%.2f GiB)
```

サイズ表示は `want / 2^30` GiB です。arena 用に後置される追加 blob の padding は `want` に含まれないため、checksum の対象外です。この出力は checksum の採取のみで、期待値との照合、警告、エラー化はしません。

## 根拠

- `sycl/src/core/expert_source.cpp:3311-3315,3350-3385` — `ArenaExpertSource::open()` の入口と `STRATA_ARENA_MMAP` 有効時の既存 padded arena の早期 map return。
- `sycl/src/program/generate.cpp:4186-4203,4204-4219,4237-4257` — streaming、mmap、通常 arena の分岐と `open()` 呼び出し。
- `sycl/src/core/expert_source.cpp:3504-3512` — 読み込み byte 数の確認後に環境変数を検査し、`want` byte の checksum を stderr に出す箇所。
- `sycl/src/core/pinned.dp.cpp:287-294` — 使用する FNV-1a 64-bit の実装。
- `docs/DETAILS.md` — `STRATA_VERIFY_ARENA` の説明は見つからず、コードに対応する測定値や利用者向け記載は確認できませんでした。
