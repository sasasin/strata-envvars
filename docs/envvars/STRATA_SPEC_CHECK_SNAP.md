# `STRATA_SPEC_CHECK_SNAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`strata-inkling --spec-check` の通常生成（plain B=1）部分で、プロンプトの prefill 後かつ最初の decode 前に slot の snapshot を追加実行する診断用スイッチです。ソースコメントは ShortConv snapshot による値を変えない作業を挟み、その後の回答が変化しないことを確認する目的を示しています。環境変数が変えるのはこの追加呼び出しの有無で、snapshot が生成 token や logits を直接設定する処理はありません（`engine/src/inkling2/ink_main.cpp:632-651`）。

## 値と判定

`std::getenv` で設定有無を調べ、値が存在し、先頭文字 `e[0]` が `'1'` の場合だけ有効です。文字列全体の比較や数値 parse はしません。したがって未設定・空文字・`0`・`true`・先頭が空白の ` 1` は無効、`1`・`10`・`1anything` は有効です。大文字小文字は関係しません。無効値への警告や fallback 処理はありません（`engine/src/inkling2/ink_main.cpp:640-641`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| `cmd_spec_check` の plain B=1 実行 | snapshot を追加しない | 先頭文字が `1`（`1`, `10`, `1anything`） | 空文字、`0`, `true`, ` 1` |

## 有効になる条件

- `--spec-check N` が正の `N` で選択され、`--prompt-ids` による ID 入力が受理される必要があります。`--spec-check` は `spec_check_n > 0` の分岐から `cmd_spec_check` を呼び、その関数の中でのみ環境変数参照箇所を通ります（`engine/src/inkling2/ink_main.cpp:966-968`, `1062-1069`）。
- モデルの open、backend の初期化、slot 確保、prefill が成功し、`run_plain` の snapshot 行まで到達する必要があります。これらの失敗経路はそれぞれ `open: ...`、`init: ...`、`alloc_slot: ...`、`prefill: ...` を stderr に出し、spec-check を失敗終了します（`engine/src/inkling2/ink_main.cpp:603-627`）。
- snapshot 実行側は backend や slot の状態により何もしない場合があります。たとえば CUDA 実装は未初期化、slot 範囲外、layer-split 有効、snapshot buffer 不在なら即時 return します（`engine/src/inkling2/cuda/ink_cuda_backend.cu:634-641`）。
- この環境変数を読む箇所には OS、backend、build macro、サーバーモード、別環境変数による値判定の分岐はありません。各 backend の snapshot 実装上の制約は上記のように別途あります。

## 実行時の詳細

値は `run_plain` 内の関数ローカル `static const bool` を初めて初期化するときに読み取られます。`cmd_spec_check` は plain B=1 の同一関数を2回実行するため、同じプロセス内では最初の読み取り結果を両方で使い、実行中に環境を変更しても再評価しません（`engine/src/inkling2/ink_main.cpp:632-641`, `656-658`）。各 plain 実行では prefill 直後、decode loop の前に `backend->snapshot_slot(0)` を呼びます。snapshot API は戻り値を持たず、この箇所で失敗を検査したり環境変数固有のエラーを出したりしません（`engine/src/inkling2/ink_backend.h:90`, `engine/src/inkling2/ink_main.cpp:641-647`）。

この追加処理は plain B=1 の二回の比較に入ります。speculative loop と verify-window 比較は後続の別ブロックで行われるため、この環境変数による追加 snapshot はそこには適用されません（`engine/src/inkling2/ink_main.cpp:656-658`, `672-706`, `745-765`）。

## ログと測定値

環境変数の読み取りや snapshot に専用ログはありません。通常の spec-check は token / logits hash の比較結果、fingerprint、各比較結果を stdout に出し、差異があれば終了コード 1 を返します（`engine/src/inkling2/ink_main.cpp:658-670`, `745-815`）。この環境変数について資料に記載された測定値は確認できません。

## 根拠

- `engine/src/inkling2/ink_main.cpp:599-651` — spec-check のモデル準備、plain B=1 実行、値の読み取りと snapshot 呼び出し。
- `engine/src/inkling2/ink_main.cpp:656-706` — plain 比較の呼び出しと、その後の speculative loop。
- `engine/src/inkling2/ink_main.cpp:966-968,1062-1069` — `--spec-check` の解析、prompt IDs 要件、実行分岐。
- `engine/src/inkling2/ink_backend.h:90` — backend snapshot API。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:634-641` — CUDA backend の snapshot ガード。
