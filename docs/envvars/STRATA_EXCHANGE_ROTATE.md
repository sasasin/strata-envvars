# `STRATA_EXCHANGE_ROTATE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（`2026-10-12` 時点）。

## 役割

常駐 RAM の expert complement と GPU cache の adaptive swap で、退避した expert のバイト列を RAM 側の旧 expert スロットへ `memcpy` する代わりに、交換用バッファの所有権を resident expert に移す機能を要求する。GPU への転送や adaptive swap の選択を変える設定ではない。通常の resident mode を有効にする設定でもない。

## 値と判定

| 環境変数 | 判定 |
|---|---|
| 未設定 | 回転を要求しない。従来のコピー経路。 |
| `1` | 回転を要求する。ただし後述の適用条件を満たさなければコピー経路へ戻る。 |
| 空文字、`0`、`01`、`true` など | 回転を要求しない。文字列全体を `strcmp(..., "1")` で比較するため、数値変換や前後空白の除去はない。 |

値は `FileExpertSource::reserve_exchanges` が交換バッファを新たに確保するときに読み取られる。要求数が現在の容量以下なら関数は先に成功して戻り、環境変数を読み直さない。このため、少なくとも最初に容量を確保する呼び出しより前に設定する必要がある。エンジン起動後に値を変更しても、既に確保した容量の回転状態は切り替わらない。

## 有効になる条件

回転の初期化には、次の条件がすべて必要。

- `--resident-experts` などで resident RAM complement が構築され、`reserve_exchanges` が呼ばれること。生成コードは `resident_ok` の場合に交換容量を確保する。
- 全 layer の expert block が同一サイズであること。
- complement が完全に pinned され、partial complement ではなく、host pointer と device pointer alias があり、サイズが正であること。
- 交換用バッファの pinned allocation が成功し、device alias を取得できること。
- 所有権テーブルの初期化が成功すること。

一つでも満たさなければ、回転は有効にならずコピー経路を維持する。要求時に利用できない場合は stderr に `FileExpertSource: exchange rotation unavailable; retaining copy path: ...` と理由を出す。初期化に成功すると `FileExpertSource: exchange buffer rotation enabled: ...; no host commit memcpy` を出す。resident mode を使わない場合、または adaptive swap が無効で交換容量を予約しない場合、この変数だけでは回転処理は行われない。

## 実行時の詳細

CUDA 実装と SYCL 実装の両方に同じ `STRATA_EXCHANGE_ROTATE` の判定と適格性条件がある。適格な場合、`ExchangeStorage` は resident と exchange の host/device pointer ペアを登録する。GPU cache への転送が完了した後の commit で、expert と spare slot の slot ID を入れ替える。回転中の `resident_blob` はこの所有権テーブルを通じて現 slot を返すため、expert bytes 自体を RAM の旧位置へコピーしない。既存の配列所有者は `FileExpertSource::close()` まで allocation を保持する。

通常の `commit_exchanges` と async adaptive の `commit_flip` のどちらも同じ slot ownership 更新を使う。回転有効時、`commit_copies` はコピーを行わず、所有権更新は `commit_flip` で行う。commit が不整合を検出した場合、stderr に `FileExpertSource: invalid exchange rotation commit; refusing corrupt residency` を出して `abort` する。通常の GPU 転送完了と commit の順序は既存どおり必要で、この設定は追加の並行実行や同期方式を導入しない。

サーバー診断は回転が active の場合に、累積 block 数と `host memcpy` 回避バイト数を stderr に表示する。バイト数は回避した memcpy payload の一回分で、read/write 両方を合算した値ではなく、GPU transfer の量も含まない。

## 根拠

- `src/core/expert_source.cpp:3226-3283`: 容量確保、環境変数の完全一致判定、uniform/pinned/mapped 条件、回転初期化と有効・fallback ログ。
- `include/strata/core/exchange_storage.hpp:24-67, 70-95`: slot/pointer 登録、atomic slot ID による resident lookup と commit 時の所有権更新。
- `src/core/expert_source.cpp:3215-3223, 3286-3304, 3320-3380`: resident lookup、交換ステージング、通常 commit と async commit の処理。
- `sycl/src/core/expert_source.cpp:2187-2268, 2318-2359`: SYCL 側の同等の判定と commit 経路。
- `src/program/generate.cpp:6724-6779`: resident complement の成功後に交換容量を確保する条件と async 時の容量予約。
- `src/program/generate.cpp:12287-12301`: resident RAM と回転統計の診断出力。
- `docs/DETAILS.md:180-182` と `docs/EXCHANGE_ROTATION.md:11-37, 39-47`: 設定の説明、診断、所有権・同期の設計資料。後者の測定節は過去の明示されたハードウェア・モデル・設定での単一 A/B を記述しており、現 HEAD での再測定や一般的な速度向上を示すものではない。
