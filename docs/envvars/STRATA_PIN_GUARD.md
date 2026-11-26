# `STRATA_PIN_GUARD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Linux で resident expert cache complement を page-lock するとき、モデルファイルのページキャッシュ解放と RAM を段階的に確保して登録する paced path を選ぶ判定を変える。設定値 `0` は通常の自動 guard 判定を止め、`2` は paced path を常に選ぶ。unset や `0` 以外の値では、空き RAM と予約量から自動判定する。適用箇所は `FileExpertSource::pin_cache_complement` で、生成処理から `--resident-experts` などの resident RAM copy を作るときに呼ばれる（`engine/src/core/expert_source.cpp:3985-4003,4311-4356`; `engine/src/program/generate.cpp:4220-4228,4242-4257,12077-12080`）。

この変数は resident copy や page-lock 自体を有効にはしない。`pin` が false の経路では値を読まない。読み取りと分岐は `#if defined(__linux__)` 内にあり、Linux 以外ではこの変数による分岐はない（`engine/src/core/expert_source.cpp:4328-4333,4369-4373`）。

## 値と判定

値は `std::getenv` で取得し、未設定なら `1`、設定されていれば `std::atoi` の戻り値を使う。文字列全体の検証はなく、`atoi` が先頭の空白と符号に続く数字列を変換し、数字列以降を無視する。したがって空文字、数字で始まらない文字列、`0anything` は `0`、`1`, `1x`, `-1`, `3` はそれぞれ非ゼロになる。`true` / `false` はどちらも `0` になる。数値としての範囲検査やエラー報告はない（`engine/src/core/expert_source.cpp:4330-4333`）。

| 条件 | unset | 設定時に paced path を選ぶ値 | 設定時に自動 guard を無効にする値 |
|---|---|---|---|
| Linux、resident complement があり `pin=true` | `1` として自動判定 | `atoi` 結果がちょうど `2`（例: `2`, `2x`） | `atoi` 結果が `0`（例: `0`, 空文字, `false`, `0anything`） |
| 上記以外の `atoi` 結果 | — | NUMA placement が成立する場合を除き、値だけでは強制しない | 結果が非ゼロなら自動判定を行う |
| Linux 以外、`pin=false`、または complement の `bytes==0` | 読み取りなし | 読み取りなし | 読み取りなし |

`guard == 2` だけが値による強制 paced path である。`guard != 0` の他の値は自動判定を有効にするが、それ自体では paced path を強制しない（`engine/src/core/expert_source.cpp:4311,4328-4356`）。

## 有効になる条件

- 実行が Linux であり、resident complement の割当量が正で、呼び出し側が `pin=true` を渡す必要がある。`--resident-experts` は `STRATA_RESIDENT_PIN` を通じて pin を選び、正の `--resident-budget-gib` / `--ram-experts-gb` も同じ環境変数を読む。`STRATA_RESIDENT_PIN=0` などで pin を無効にすると guard は読まれず、通常の pageable resident allocation に進む（`engine/src/program/generate.cpp:4220-4228,4242-4257`; `engine/src/core/expert_source.cpp:4311,4328-4333,4374-4403`）。
- 未設定（`guard=1`）または設定値の `atoi` 結果が `0` と `2` 以外のときは、`free_memory_bytes` が成功し、`detail::pin_depends_on_reclaim(free_now, bytes, pace_reserve)` が真なら、自動でモデルファイルの cache を解放する。解放後に同じ条件を再評価し、まだ真なら paced path にする。`guard=0` ではこの自動判定とそれに伴う通常の cache drop は行わない（`engine/src/core/expert_source.cpp:4351-4367`）。
- `STRATA_PIN_GUARD=2` は `pin=true` の Linux 経路で常に paced path を選ぶ。Linux 上で NUMA placement が成立した場合は値にかかわらず paced path となり、ファイル cache を先に解放する。`guard=0` なら `STRATA_PIN_GUARD=0 overridden: NUMA placement needs the paced path` と stderr に出る（`engine/src/core/expert_source.cpp:4328-4354`）。NUMA placement の準備は active split が on かつ test でなく、pack の role byte 情報・2 つの slice の core/node 条件が満たされる場合に限られる。満たされない場合は placement を失敗として記録し、通常配置に戻る（`engine/src/core/expert_source.cpp:669-712`）。
- paced path の予約量は別変数 `STRATA_PIN_RESERVE_GIB` が設定され、`atof(v) > 0` の場合はその GiB 値を使う。それ以外（未設定、空文字、ゼロ、負値、数値に変換できない文字列）は `max(headroom_bytes, 2 GiB)` が使われる。`guard=2` であっても、この予約を割当ステップ後に保てない場合は全量を page-lock できないことがある（`engine/src/core/expert_source.cpp:4323-4327,4457-4465`）。

## 実行時の詳細

`pin_cache_complement` は GPU expert cache が open かつ fully filled であることを確認し、device synchronize 後に complement のサイズを計算する。`bytes > 0` の allocation block で `STRATA_PIN_RESERVE_GIB` を読み、Linux の `pin` 経路に入るときに `STRATA_PIN_GUARD` を初めて読む。guard は関数内の `static const int` なので、最初にこの分岐へ到達した時点の値をプロセス内で再利用し、その後の呼び出しで環境を変更しても再読込しない（`engine/src/core/expert_source.cpp:3985-4003,4311-4335`）。

`guard=2` または NUMA placement 成立時は `paced=true` となり、通常の一括 `cudaHostAlloc` を通らない。代わりに host arena を確保し、予約量を下回らない範囲で最大 1 GiB ずつページを fault-in し、expert blob 境界に合わせて prefix を登録する。予約を保てないとその位置で停止し、残りは resident だが pageable のままになる（`engine/src/core/expert_source.cpp:4374-4429,4450-4526`）。自動判定が偽、または guard が `0` で NUMA placement もないときは一括 `cudaHostAlloc` を試す。失敗時は pageable memory に fallback する（`engine/src/core/expert_source.cpp:4374-4403`）。

コマンドラインと他の設定の関係では、`--ssd-experts` または budget `0` は resident pin を無効にし、guard の評価に到達しない。正の budget や `--resident-experts` が resident path を選んでも、page-lock の可否は `STRATA_RESIDENT_PIN` 側が決め、その後の Linux pin 経路でこの guard が allocation 方法を選ぶ。CLI に guard の直接上書き引数はない（`engine/src/program/generate.cpp:4220-4228,4236-4257,12077-12080`）。

## ログと測定値

- NUMA placement 成立時は `FileExpertSource: NUMA placement: the model files' cached pages were released; free after the drop: ...` を出す。guard が `0` なら前述の上書き警告も出る（`engine/src/core/expert_source.cpp:4335-4349`）。
- `guard=2` で paced path に入ると `FileExpertSource: STRATA_PIN_GUARD=2: page-locking the complement in steps` を出す。NUMA placement が理由の場合は `STRATA_NUMA_SPLIT` が表示される（`engine/src/core/expert_source.cpp:4351-4354`）。
- 自動判定が cache drop を行うと、解放前後の実空き RAM を示す `FileExpertSource: ... really free ...; the model files' cached pages were released: ...` が出る。さらに他ファイルの cache reclaim に依存する paced path なら `FileExpertSource: the rest comes from reclaimed cache of other files: page-locking it in steps, as far as the RAM allows (#1250)` を出す（`engine/src/core/expert_source.cpp:4355-4367`）。
- paced path で全量を登録できない場合は `WARNING: only ... could be page-locked (...); the rest is resident but pageable, so its copies to the GPU go through the CPU (#1250)` を出す。割当失敗や expert read 失敗は `pin_cache_complement` が false とエラー文字列を返し、呼び出し元で resident soft fallback を試みるか、通常の resident fallback に進む（`engine/src/core/expert_source.cpp:4515-4526,4423-4429,4687-4691`; `engine/src/program/generate.cpp:12091-12106,12209-12213`）。

`docs/TROUBLESHOOTING.md:271-279` は `STRATA_PIN_GUARD=0` で guard を止めると説明している。現行実装では Linux の active NUMA placement が成立すると `0` でも cache drop と paced path を強制するため、その条件では説明に例外がある。測定値はこの変数の挙動として記載していない。

## 根拠

- `engine/src/core/expert_source.cpp:3985-4003` — complement の事前条件と関数。
- `engine/src/core/expert_source.cpp:4311-4373` — 予約量、Linux 限定の guard parse、NUMA / 自動判定、cache drop と paced 分岐。
- `engine/src/core/expert_source.cpp:4374-4403,4450-4526` — 一括 allocation と fallback、paced allocation・登録・警告。
- `engine/src/core/expert_source.cpp:4687-4691` — copy failure の戻り方。
- `engine/src/program/generate.cpp:4220-4228,4236-4257,12077-12106` — CLI / `STRATA_RESIDENT_PIN` による適用条件と呼び出し。
- `engine/src/core/expert_source.cpp:669-712` — NUMA placement の成立条件。
